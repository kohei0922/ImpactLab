from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from .errors import AnalysisError
from .schemas import SummarizeResponse

OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4.1-mini"


SUMMARY_JSON_SCHEMA: dict[str, Any] = {
    "name": "impactlab_summary",
    "strict": True,
    "schema": {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "summary": {
                "type": "string",
                "description": "分析結果の全体要約（2-4文）",
            },
            "warnings": {
                "type": "array",
                "items": {"type": "string"},
                "description": "解釈上の注意点",
            },
            "next_steps": {
                "type": "array",
                "items": {"type": "string"},
                "description": "次に取るべき実務アクション",
            },
        },
        "required": ["summary", "warnings", "next_steps"],
    },
}


def summarize_status() -> tuple[bool, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if key:
        return (True, "OPENAI_API_KEY が設定されています。")
    return (
        False,
        "OPENAI_API_KEY が未設定です。環境変数を設定するとインサイト要約を使えます。",
    )


def _build_prompt(config: dict[str, Any], analysis: dict[str, Any]) -> str:
    did = analysis.get("did", {})
    counts = analysis.get("counts", {})
    diagnostics = analysis.get("diagnostics", {})
    effect_series = analysis.get("series", {}).get("effect_series", [])

    recent_effect = effect_series[-1] if effect_series else {}
    return (
        "以下は施策効果分析の結果です。数値根拠に基づいて要約してください。\n"
        "要求:\n"
        "- summary: 2-4文で主要な示唆を述べる\n"
        "- warnings: 過剰解釈を避ける注意点を最大3点\n"
        "- next_steps: 実務的な次アクションを最大3点\n"
        "- 日本語で簡潔に\n"
        "- 画面上に既に出ている数値を繰り返し列挙しない\n"
        "- 具体数値より、意味合い・背景仮説・打ち手を優先する\n\n"
        f"設定: {json.dumps(config, ensure_ascii=False)}\n"
        f"DID: {json.dumps(did, ensure_ascii=False)}\n"
        f"Counts: {json.dumps(counts, ensure_ascii=False)}\n"
        f"Diagnostics: {json.dumps(diagnostics, ensure_ascii=False)}\n"
        f"Latest effect point: {json.dumps(recent_effect, ensure_ascii=False)}\n"
    )


def _extract_content(message_content: Any) -> str:
    if isinstance(message_content, str):
        return message_content

    if isinstance(message_content, list):
        # Some API variants return content blocks.
        for item in message_content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str):
                    return text

    raise AnalysisError(
        "OpenAIレスポンス形式を解釈できませんでした。",
        ["message.content からJSONテキストを抽出できません。"],
        status_code=502,
    )


def generate_summary(config: dict[str, Any], analysis: dict[str, Any]) -> SummarizeResponse:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AnalysisError(
            "OPENAI_API_KEY が未設定です。",
            ["環境変数 OPENAI_API_KEY を設定してから再実行してください。"],
            status_code=400,
        )

    model = os.getenv("OPENAI_MODEL", DEFAULT_MODEL).strip() or DEFAULT_MODEL
    prompt = _build_prompt(config, analysis)

    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "あなたは因果推論の実務アナリストです。"
                    "必ずJSON Schemaに厳密準拠し、"
                    "数値の再掲よりも意思決定に使える示唆を優先してください。"
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": SUMMARY_JSON_SCHEMA,
        },
    }

    req = request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
    except error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8")
        except Exception:
            body = ""
        raise AnalysisError(
            "OpenAI API呼び出しに失敗しました。",
            [
                f"HTTP {exc.code}: {exc.reason}",
                f"response: {body[:400]}",
            ],
            status_code=502,
        ) from exc
    except Exception as exc:
        raise AnalysisError(
            "OpenAI APIへの接続に失敗しました。",
            [f"接続エラー: {exc}"],
            status_code=502,
        ) from exc

    try:
        data = json.loads(raw)
        choices = data.get("choices", [])
        if not choices:
            raise AnalysisError(
                "OpenAIから有効な候補が返されませんでした。",
                ["choices が空です。"],
                status_code=502,
            )
        message = choices[0].get("message", {})
        content = _extract_content(message.get("content"))
        parsed = json.loads(content)
        result = SummarizeResponse(
            summary=parsed.get("summary", ""),
            warnings=list(parsed.get("warnings", [])),
            next_steps=list(parsed.get("next_steps", [])),
        )
    except AnalysisError:
        raise
    except Exception as exc:
        raise AnalysisError(
            "OpenAIレスポンスのJSON解析に失敗しました。",
            [f"解析エラー: {exc}", f"raw response: {raw[:500]}"],
            status_code=502,
        ) from exc

    if not result.summary.strip():
        raise AnalysisError(
            "インサイト要約が空で返されました。",
            ["入力データを確認して再実行してください。"],
            status_code=502,
        )

    return result
