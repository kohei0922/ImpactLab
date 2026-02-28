from __future__ import annotations

import difflib
from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .errors import AnalysisError
from .schemas import DiagnosticsResult

TRUTHY_TREATED = {"1", "true", "t", "yes", "y", "treated"}
FALSY_TREATED = {"0", "false", "f", "no", "n", "control"}


def _normalize_treated_value(value: object) -> float:
    if pd.isna(value):
        return np.nan

    if isinstance(value, (int, np.integer)):
        if value in (0, 1):
            return float(value)
        return np.nan

    if isinstance(value, float):
        if value in (0.0, 1.0):
            return value
        return np.nan

    text = str(value).strip().lower()
    if text in TRUTHY_TREATED:
        return 1.0
    if text in FALSY_TREATED:
        return 0.0
    return np.nan


def _column_suggestions(target: str, available: list[str]) -> list[str]:
    return difflib.get_close_matches(target, available, n=3, cutoff=0.3)


def validate_and_prepare(
    df: pd.DataFrame,
    unit_col: str,
    time_col: str,
    y_col: str,
    treated_col: str,
) -> tuple[pd.DataFrame, dict[str, float], int]:
    required = [unit_col, time_col, y_col, treated_col]
    available = [str(col) for col in df.columns]

    missing = [col for col in required if col not in available]
    if missing:
        details: list[str] = []
        for col in missing:
            suggestions = _column_suggestions(col, available)
            if suggestions:
                details.append(f"'{col}' 列が見つかりません。候補: {', '.join(suggestions)}")
            else:
                details.append(
                    f"'{col}' 列が見つかりません。利用可能な列: {', '.join(available)}"
                )
        raise AnalysisError("必要な列が見つかりません。", details)

    missing_rates = {
        col: round(float(df[col].isna().mean() * 100.0), 2) for col in required
    }

    work = df[required].copy()
    for col in required:
        work[col] = work[col].replace(r"^\s*$", np.nan, regex=True)

    dropped_rows = int(work.isna().any(axis=1).sum())
    work = work.dropna(subset=required)

    if work.empty:
        raise AnalysisError(
            "必要列に有効なデータ行がありません。",
            [
                "unit/time/y/treated のいずれかが欠損している行しかありません。",
                "欠損を補完するか、欠損行を取り除いたCSVを再アップロードしてください。",
            ],
        )

    unit_series = work[unit_col].astype(str).str.strip()
    invalid_unit = unit_series.eq("") | unit_series.str.lower().eq("nan")
    if invalid_unit.any():
        raise AnalysisError(
            "unit列に無効な値があります。",
            [
                f"無効なunitが {int(invalid_unit.sum())} 行あります。",
                "unitは空文字でない識別子を設定してください。",
            ],
        )

    raw_time = work[time_col].copy()
    parsed_time = pd.to_datetime(raw_time, errors="coerce")
    if parsed_time.isna().any():
        examples = (
            raw_time[parsed_time.isna()]
            .astype(str)
            .drop_duplicates()
            .head(3)
            .tolist()
        )
        raise AnalysisError(
            f"{time_col} 列の日付を解釈できません。",
            [
                f"日付変換に失敗した行数: {int(parsed_time.isna().sum())}",
                f"失敗例: {', '.join(examples)}",
                "YYYY-MM-DD 形式を推奨します。",
            ],
        )

    raw_y = work[y_col].copy()
    parsed_y = pd.to_numeric(raw_y, errors="coerce")
    if parsed_y.isna().any():
        examples = raw_y[parsed_y.isna()].astype(str).drop_duplicates().head(3).tolist()
        raise AnalysisError(
            f"{y_col} 列を数値に変換できません。",
            [
                f"数値変換に失敗した行数: {int(parsed_y.isna().sum())}",
                f"失敗例: {', '.join(examples)}",
                "y列は数値のみを含めてください。",
            ],
        )

    raw_treated = work[treated_col].copy()
    parsed_treated = raw_treated.map(_normalize_treated_value)
    if parsed_treated.isna().any():
        examples = (
            raw_treated[parsed_treated.isna()]
            .astype(str)
            .drop_duplicates()
            .head(5)
            .tolist()
        )
        raise AnalysisError(
            f"{treated_col} 列を0/1に変換できません。",
            [
                "treatedには 0/1, true/false, yes/no, treated/control を使用してください。",
                f"変換失敗例: {', '.join(examples)}",
            ],
        )

    clean = pd.DataFrame(
        {
            "unit": unit_series,
            "time": parsed_time,
            "y": parsed_y.astype(float),
            "treated": parsed_treated.astype(int),
        }
    )

    unit_consistency = clean.groupby("unit")["treated"].nunique()
    unstable_units = unit_consistency[unit_consistency > 1].index.tolist()
    if unstable_units:
        preview = ", ".join(unstable_units[:5])
        raise AnalysisError(
            "treated列はunitごとに一定である必要があります。",
            [
                f"treatedが期間中に変化しているunit例: {preview}",
                "同じunitでは、treatedは常に0または常に1にしてください。",
            ],
        )

    if clean["treated"].nunique() < 2:
        raise AnalysisError(
            "treated列に0群と1群の両方が必要です。",
            [
                "treated=0のコントロール群とtreated=1の処置群を含めてください。",
            ],
        )

    if clean["unit"].nunique() < 2:
        raise AnalysisError(
            "unitが不足しています。",
            [
                "DIDには複数unitが必要です。",
                "少なくとも2つ以上の異なるunitを含めてください。",
            ],
        )

    clean = clean.sort_values(["time", "unit"]).reset_index(drop=True)
    return clean, missing_rates, dropped_rows


def _count_outliers_iqr(series: pd.Series) -> int:
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return int(((series < lower) | (series > upper)).sum())


def _check_pretrend(df: pd.DataFrame, policy_ts: pd.Timestamp) -> tuple[str, str | None]:
    pre_df = df[df["time"] < policy_ts]
    grouped = pre_df.groupby(["time", "treated"], as_index=False)["y"].mean()
    pivot = grouped.pivot(index="time", columns="treated", values="y").dropna()

    if len(pivot) < 6 or 0 not in pivot.columns or 1 not in pivot.columns:
        return (
            "warn",
            "平行トレンド診断に必要な施策前データが不足しています。",
        )

    diff = (pivot[1] - pivot[0]).astype(float)
    trend = np.arange(len(diff), dtype=float)
    design = sm.add_constant(trend, has_constant="add")

    try:
        model = sm.OLS(diff.to_numpy(dtype=float), design).fit()
    except Exception:
        return (
            "warn",
            "平行トレンド診断を計算できませんでした。データの粒度を確認してください。",
        )

    slope = float(model.params[1])
    p_value = float(model.pvalues[1])
    if p_value < 0.10 and abs(slope) > 0.02:
        return (
            "warn",
            "施策前にtreated-control差のトレンドが見られます。平行トレンド仮定に注意してください。",
        )
    return ("ok", None)


def build_diagnostics(
    df: pd.DataFrame,
    policy_start: date,
    missing_rates: dict[str, float],
    dropped_rows: int,
) -> DiagnosticsResult:
    policy_ts = pd.Timestamp(policy_start)
    pre_periods = int(df.loc[df["time"] < policy_ts, "time"].nunique())
    post_periods = int(df.loc[df["time"] >= policy_ts, "time"].nunique())

    messages: list[str] = []
    if dropped_rows > 0:
        messages.append(
            f"必須列の欠損により {dropped_rows} 行を分析対象から除外しました。"
        )

    for col, rate in missing_rates.items():
        if rate > 0:
            messages.append(f"{col} の欠損率は {rate:.2f}% です。")

    if pre_periods < 8:
        messages.append(
            f"施策前データが {pre_periods} 週しかありません。推定が不安定になる可能性があります。"
        )

    if post_periods < 4:
        messages.append(
            f"施策後データが {post_periods} 週しかありません。効果の持続性評価には不足しています。"
        )

    unique_times = df["time"].drop_duplicates().sort_values()
    if len(unique_times) >= 2:
        median_gap = float(unique_times.diff().dropna().dt.days.median())
        if abs(median_gap - 7.0) > 1.0:
            messages.append(
                "time列の間隔が週次ではない可能性があります。週次データを推奨します。"
            )

    outlier_count = _count_outliers_iqr(df["y"])
    if outlier_count > 0:
        messages.append(
            f"y列にIQR基準で外れ値候補が {outlier_count} 件あります。"
        )

    pretrend_flag, pretrend_message = _check_pretrend(df, policy_ts)
    if pretrend_message:
        messages.append(pretrend_message)

    return DiagnosticsResult(
        pretrend_flag=pretrend_flag,
        messages=messages,
        missing_rates=missing_rates,
        outlier_count=outlier_count,
        pre_periods=pre_periods,
        post_periods=post_periods,
    )

