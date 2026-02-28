from __future__ import annotations

import pandas as pd
import statsmodels.api as sm

from .errors import AnalysisError
from .schemas import DidResult


def run_did_regression(df: pd.DataFrame) -> DidResult:
    if df["post"].nunique() < 2:
        raise AnalysisError(
            "post列に施策前後の両方が必要です。",
            ["policy_startがデータ期間外の可能性があります。"],
        )

    if df["treated"].nunique() < 2:
        raise AnalysisError(
            "treated列に0群と1群の両方が必要です。",
            ["treated=0のcontrolとtreated=1のtreatedが必要です。"],
        )

    design = df[["treated", "post", "treated_post"]].astype(float)
    design = sm.add_constant(design, has_constant="add")
    outcome = df["y"].astype(float)

    try:
        model = sm.OLS(outcome, design).fit(cov_type="HC3")
    except Exception as exc:
        raise AnalysisError(
            "DID回帰の計算に失敗しました。",
            [f"統計モデルエラー: {exc}"],
        ) from exc

    if "treated_post" not in model.params.index:
        raise AnalysisError(
            "DIDの主要係数を取得できませんでした。",
            ["treated*post項がモデルに含まれているか確認してください。"],
        )

    ci_table = model.conf_int()
    ci_low = float(ci_table.loc["treated_post", 0])
    ci_high = float(ci_table.loc["treated_post", 1])

    return DidResult(
        ate=float(model.params["treated_post"]),
        ci_low=ci_low,
        ci_high=ci_high,
        p_value=float(model.pvalues["treated_post"]),
    )

