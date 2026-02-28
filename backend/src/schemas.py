from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class AnalyzeRequest(BaseModel):
    csv: str = Field(..., min_length=1, description="Raw CSV string")
    unit_col: str = Field(..., min_length=1)
    time_col: str = Field(..., min_length=1)
    y_col: str = Field(..., min_length=1)
    treated_col: str = Field(..., min_length=1)
    policy_start: date

    @field_validator("csv")
    @classmethod
    def csv_must_not_be_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("csv は空文字を許可しません。")
        return value

    @field_validator("unit_col", "time_col", "y_col", "treated_col")
    @classmethod
    def column_name_must_not_be_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("列名は空文字を許可しません。")
        return stripped


class DidResult(BaseModel):
    ate: float
    ci_low: float
    ci_high: float
    p_value: float


class CountsResult(BaseModel):
    n_obs: int
    n_units: int
    n_units_treated: int
    n_units_control: int


class GroupMeanPoint(BaseModel):
    t: str
    treated_mean: float
    control_mean: float


class PredActualPoint(BaseModel):
    t: str
    y_actual: float
    y_pred: float


class EffectPoint(BaseModel):
    t: str
    effect: float
    cum_effect: float


class SeriesResult(BaseModel):
    group_means: list[GroupMeanPoint]
    pred_vs_actual: list[PredActualPoint]
    effect_series: list[EffectPoint]


class DiagnosticsResult(BaseModel):
    pretrend_flag: Literal["ok", "warn"] = "ok"
    messages: list[str] = Field(default_factory=list)
    missing_rates: dict[str, float] = Field(default_factory=dict)
    outlier_count: int = 0
    pre_periods: int = 0
    post_periods: int = 0


class AnalyzeResponse(BaseModel):
    did: DidResult
    counts: CountsResult
    series: SeriesResult
    diagnostics: DiagnosticsResult
    report_token: str | None = None


class ReportRequest(BaseModel):
    token: str | None = None
    config: AnalyzeRequest | None = None
    analysis: AnalyzeResponse | None = None

    @model_validator(mode="after")
    def require_token_or_payload(self) -> "ReportRequest":
        if self.token:
            return self
        if self.config is None or self.analysis is None:
            raise ValueError(
                "token を指定するか、config と analysis の両方を指定してください。"
            )
        return self


class ErrorResponse(BaseModel):
    message: str
    details: list[str] = Field(default_factory=list)

