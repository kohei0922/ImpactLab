from __future__ import annotations

from datetime import date

import pandas as pd

from .errors import AnalysisError
from .schemas import CountsResult, GroupMeanPoint


def add_post_column(df: pd.DataFrame, policy_start: date) -> pd.DataFrame:
    policy_ts = pd.Timestamp(policy_start)
    transformed = df.copy()
    transformed["post"] = (transformed["time"] >= policy_ts).astype(int)
    transformed["treated_post"] = transformed["treated"] * transformed["post"]
    return transformed


def build_counts(df: pd.DataFrame) -> CountsResult:
    unit_flags = df.groupby("unit", as_index=False)["treated"].max()
    n_units_treated = int((unit_flags["treated"] == 1).sum())
    n_units_control = int((unit_flags["treated"] == 0).sum())

    return CountsResult(
        n_obs=int(len(df)),
        n_units=int(df["unit"].nunique()),
        n_units_treated=n_units_treated,
        n_units_control=n_units_control,
    )


def build_group_means(df: pd.DataFrame) -> list[GroupMeanPoint]:
    grouped = (
        df.groupby(["time", "treated"], as_index=False)["y"]
        .mean()
        .sort_values(["time", "treated"])
    )

    treated = grouped[grouped["treated"] == 1][["time", "y"]].rename(
        columns={"y": "treated_mean"}
    )
    control = grouped[grouped["treated"] == 0][["time", "y"]].rename(
        columns={"y": "control_mean"}
    )

    merged = pd.merge(treated, control, on="time", how="inner").sort_values("time")

    if merged.empty:
        raise AnalysisError(
            "group_meansを作成できませんでした。",
            ["treated群とcontrol群が同じ週に存在するデータが必要です。"],
        )

    points: list[GroupMeanPoint] = []
    for row in merged.itertuples(index=False):
        points.append(
            GroupMeanPoint(
                t=row.time.strftime("%Y-%m-%d"),
                treated_mean=float(row.treated_mean),
                control_mean=float(row.control_mean),
            )
        )
    return points

