from __future__ import annotations

import logging
import uuid
from collections import OrderedDict
from time import perf_counter
from typing import Any

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse

from backend.src.analyze_did import run_did_regression
from backend.src.analyze_ts import run_counterfactual
from backend.src.errors import AnalysisError
from backend.src.parse import csv_to_dataframe
from backend.src.report import render_report_html
from backend.src.schemas import (
    AnalyzeRequest,
    AnalyzeResponse,
    ErrorResponse,
    ReportRequest,
    SeriesResult,
)
from backend.src.transform import add_post_column, build_counts, build_group_means
from backend.src.validate import build_diagnostics, validate_and_prepare

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger("impactlab")

app = FastAPI(title="ImpactLab API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

REPORT_CACHE: OrderedDict[str, dict[str, Any]] = OrderedDict()
MAX_REPORT_CACHE = 50


def _timed(step_name: str, fn, *args, **kwargs):
    started = perf_counter()
    result = fn(*args, **kwargs)
    elapsed_ms = (perf_counter() - started) * 1000
    logger.info("%s completed in %.1f ms", step_name, elapsed_ms)
    return result


def _store_report_context(config: AnalyzeRequest, analysis: AnalyzeResponse) -> str:
    token = uuid.uuid4().hex
    REPORT_CACHE[token] = {
        "config": config.model_dump(mode="json"),
        "analysis": analysis.model_dump(mode="json"),
    }
    while len(REPORT_CACHE) > MAX_REPORT_CACHE:
        REPORT_CACHE.popitem(last=False)
    return token


@app.exception_handler(AnalysisError)
async def analysis_error_handler(_, exc: AnalysisError) -> JSONResponse:
    payload = ErrorResponse(message=exc.message, details=exc.details)
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
async def request_validation_error_handler(_, exc: RequestValidationError) -> JSONResponse:
    details = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        details.append(f"{location}: {err.get('msg', 'invalid input')}")
    payload = ErrorResponse(
        message="リクエスト形式が不正です。",
        details=details,
    )
    return JSONResponse(status_code=400, content=payload.model_dump())


@app.exception_handler(Exception)
async def internal_error_handler(_, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error: %s", exc)
    payload = ErrorResponse(
        message="サーバー内部でエラーが発生しました。",
        details=[
            "入力データを見直して再実行してください。",
            "解消しない場合はサーバーログを確認してください。",
        ],
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    logger.info("analyze requested: policy_start=%s", request.policy_start)

    raw_df = _timed("parse", csv_to_dataframe, request.csv)
    clean_df, missing_rates, dropped_rows = _timed(
        "validate",
        validate_and_prepare,
        raw_df,
        request.unit_col,
        request.time_col,
        request.y_col,
        request.treated_col,
    )
    model_df = _timed("transform", add_post_column, clean_df, request.policy_start)
    did_result = _timed("did", run_did_regression, model_df)
    pred_vs_actual, effect_series = _timed(
        "ts_counterfactual",
        run_counterfactual,
        model_df,
        request.policy_start,
    )

    group_means = build_group_means(model_df)
    counts = build_counts(model_df)
    diagnostics = build_diagnostics(
        model_df,
        request.policy_start,
        missing_rates,
        dropped_rows,
    )

    response = AnalyzeResponse(
        did=did_result,
        counts=counts,
        series=SeriesResult(
            group_means=group_means,
            pred_vs_actual=pred_vs_actual,
            effect_series=effect_series,
        ),
        diagnostics=diagnostics,
    )

    report_token = _store_report_context(request, response)
    response.report_token = report_token
    logger.info("analyze completed: n_obs=%s token=%s", response.counts.n_obs, report_token)
    return response


@app.get("/report", response_class=HTMLResponse)
def get_report(token: str) -> HTMLResponse:
    payload = REPORT_CACHE.get(token)
    if payload is None:
        raise AnalysisError(
            "指定されたレポートトークンが見つかりません。",
            ["先に /analyze を実行して report_token を取得してください。"],
            status_code=404,
        )

    html = _timed("report", render_report_html, payload["config"], payload["analysis"])
    return HTMLResponse(content=html)


@app.post("/report", response_class=HTMLResponse)
def post_report(request: ReportRequest) -> HTMLResponse:
    if request.token:
        payload = REPORT_CACHE.get(request.token)
        if payload is None:
            raise AnalysisError(
                "指定されたレポートトークンが見つかりません。",
                ["先に /analyze を実行して report_token を取得してください。"],
                status_code=404,
            )
        html = _timed("report", render_report_html, payload["config"], payload["analysis"])
        return HTMLResponse(content=html)

    html = _timed(
        "report",
        render_report_html,
        request.config.model_dump(mode="json"),
        request.analysis.model_dump(mode="json"),
    )
    return HTMLResponse(content=html)
