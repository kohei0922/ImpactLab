from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd
import statsmodels.api as sm

from .errors import AnalysisError
from .schemas import EffectPoint, PredActualPoint


def _build_design_matrix(series: pd.DataFrame) -> pd.DataFrame:
    trend = pd.Series(np.arange(len(series), dtype=float), index=series.index, name="trend")
    month = series["time"].dt.month.astype(str)
    seasonality = pd.get_dummies(month, prefix="m", drop_first=True, dtype=float)
    const = pd.Series(1.0, index=series.index, name="const")
    return pd.concat([const, trend, seasonality], axis=1)


def run_counterfactual(
    df: pd.DataFrame,
    policy_start: date,
) -> tuple[list[PredActualPoint], list[EffectPoint]]:
    policy_ts = pd.Timestamp(policy_start)
    treated_ts = (
        df[df["treated"] == 1]
        .groupby("time", as_index=False)["y"]
        .mean()
        .rename(columns={"y": "y_actual"})
        .sort_values("time")
        .reset_index(drop=True)
    )

    if treated_ts.empty:
        raise AnalysisError(
            "treated群の時系列がありません。",
            ["treated=1の行が存在することを確認してください。"],
        )

    pre_mask = treated_ts["time"] < policy_ts
    post_mask = ~pre_mask

    pre_points = int(pre_mask.sum())
    post_points = int(post_mask.sum())

    if pre_points < 4:
        raise AnalysisError(
            "時系列反実仮想に必要な施策前データが不足しています。",
            [f"施策前ポイント数: {pre_points}（最低4点必要）"],
        )

    if post_points < 1:
        raise AnalysisError(
            "時系列反実仮想に必要な施策後データがありません。",
            ["policy_startを見直すか、施策後データを追加してください。"],
        )

    design = _build_design_matrix(treated_ts)

    try:
        model = sm.OLS(
            treated_ts.loc[pre_mask, "y_actual"].astype(float),
            design.loc[pre_mask],
        ).fit()
    except Exception as exc:
        raise AnalysisError(
            "時系列モデルの学習に失敗しました。",
            [f"統計モデルエラー: {exc}"],
        ) from exc

    treated_ts["y_pred"] = model.predict(design)
    post_df = treated_ts.loc[post_mask].copy()
    post_df["effect"] = post_df["y_actual"] - post_df["y_pred"]
    post_df["cum_effect"] = post_df["effect"].cumsum()

    pred_vs_actual: list[PredActualPoint] = []
    for row in treated_ts.itertuples(index=False):
        pred_vs_actual.append(
            PredActualPoint(
                t=row.time.strftime("%Y-%m-%d"),
                y_actual=float(row.y_actual),
                y_pred=float(row.y_pred),
            )
        )

    effect_series: list[EffectPoint] = []
    for row in post_df.itertuples(index=False):
        effect_series.append(
            EffectPoint(
                t=row.time.strftime("%Y-%m-%d"),
                effect=float(row.effect),
                cum_effect=float(row.cum_effect),
            )
        )

    return pred_vs_actual, effect_series

