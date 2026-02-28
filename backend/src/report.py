from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Any


def _format_number(value: Any, digits: int = 4) -> str:
    if value is None:
        return "-"
    if isinstance(value, (int, float)):
        return f"{value:.{digits}f}"
    return escape(str(value))


def _render_key_value_table(items: list[tuple[str, Any]]) -> str:
    rows = []
    for key, value in items:
        rows.append(
            "<tr>"
            f"<th>{escape(key)}</th>"
            f"<td>{escape(str(value))}</td>"
            "</tr>"
        )
    return "<table class='kv-table'>" + "".join(rows) + "</table>"


def _render_series_table(
    rows: list[dict[str, Any]],
    columns: list[tuple[str, str]],
    limit: int = 12,
) -> str:
    if not rows:
        return "<p class='muted'>データなし</p>"

    head = "".join(f"<th>{escape(label)}</th>" for _, label in columns)
    body_rows = []
    for row in rows[:limit]:
        tds = "".join(f"<td>{_format_number(row.get(col))}</td>" for col, _ in columns)
        body_rows.append(f"<tr>{tds}</tr>")

    return (
        "<table class='series-table'>"
        f"<thead><tr>{head}</tr></thead>"
        f"<tbody>{''.join(body_rows)}</tbody>"
        "</table>"
    )


def render_report_html(config: dict[str, Any], analysis: dict[str, Any]) -> str:
    did = analysis.get("did", {})
    counts = analysis.get("counts", {})
    diagnostics = analysis.get("diagnostics", {})
    series = analysis.get("series", {})

    diag_messages = diagnostics.get("messages", [])
    message_html = "".join(f"<li>{escape(msg)}</li>" for msg in diag_messages)
    if not message_html:
        message_html = "<li>診断メッセージはありません。</li>"

    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"""<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>ImpactLab Report</title>
  <style>
    :root {{
      --bg: #f5f7fb;
      --ink: #1f2937;
      --muted: #5b6470;
      --card: #ffffff;
      --line: #d7dce5;
      --accent: #0f766e;
    }}
    body {{
      font-family: "Segoe UI", "BIZ UDPGothic", sans-serif;
      color: var(--ink);
      background: var(--bg);
      margin: 0;
      padding: 24px;
    }}
    .container {{
      max-width: 1040px;
      margin: 0 auto;
    }}
    h1 {{
      margin: 0 0 4px 0;
      font-size: 30px;
      letter-spacing: 0.3px;
    }}
    .sub {{
      color: var(--muted);
      margin-bottom: 20px;
    }}
    .card {{
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      margin-bottom: 14px;
    }}
    .kpi-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 10px;
      margin-top: 10px;
    }}
    .kpi {{
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px;
      background: #fbfcff;
    }}
    .kpi .label {{
      color: var(--muted);
      font-size: 12px;
    }}
    .kpi .value {{
      margin-top: 6px;
      font-size: 19px;
      font-weight: 700;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin-top: 8px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px;
      font-size: 13px;
      text-align: left;
    }}
    th {{
      background: #f1f4fa;
    }}
    .muted {{
      color: var(--muted);
    }}
    ul {{
      margin: 6px 0 0 18px;
    }}
    .tag {{
      display: inline-block;
      padding: 2px 8px;
      border-radius: 999px;
      background: #dbf7ef;
      color: #0f5132;
      font-size: 12px;
      border: 1px solid #afe4d1;
    }}
  </style>
</head>
<body>
  <div class="container">
    <h1>ImpactLab 分析レポート</h1>
    <div class="sub">生成日時: {escape(created_at)}</div>

    <section class="card">
      <h2>設定</h2>
      {_render_key_value_table([
        ("unit_col", config.get("unit_col", "-")),
        ("time_col", config.get("time_col", "-")),
        ("y_col", config.get("y_col", "-")),
        ("treated_col", config.get("treated_col", "-")),
        ("policy_start", config.get("policy_start", "-")),
      ])}
    </section>

    <section class="card">
      <h2>主要結果</h2>
      <div class="kpi-grid">
        <div class="kpi"><div class="label">ATE</div><div class="value">{_format_number(did.get("ate"), 4)}</div></div>
        <div class="kpi"><div class="label">CI Low</div><div class="value">{_format_number(did.get("ci_low"), 4)}</div></div>
        <div class="kpi"><div class="label">CI High</div><div class="value">{_format_number(did.get("ci_high"), 4)}</div></div>
        <div class="kpi"><div class="label">p-value</div><div class="value">{_format_number(did.get("p_value"), 6)}</div></div>
      </div>
      <div class="kpi-grid">
        <div class="kpi"><div class="label">n_obs</div><div class="value">{_format_number(counts.get("n_obs"), 0)}</div></div>
        <div class="kpi"><div class="label">n_units</div><div class="value">{_format_number(counts.get("n_units"), 0)}</div></div>
        <div class="kpi"><div class="label">treated units</div><div class="value">{_format_number(counts.get("n_units_treated"), 0)}</div></div>
        <div class="kpi"><div class="label">control units</div><div class="value">{_format_number(counts.get("n_units_control"), 0)}</div></div>
      </div>
    </section>

    <section class="card">
      <h2>診断</h2>
      <p>
        平行トレンド判定:
        <span class="tag">{escape(str(diagnostics.get("pretrend_flag", "ok")))}</span>
      </p>
      <ul>{message_html}</ul>
    </section>

    <section class="card">
      <h2>時系列テーブル（先頭12行）</h2>
      <h3>group_means</h3>
      {_render_series_table(
        series.get("group_means", []),
        [("t", "t"), ("treated_mean", "treated_mean"), ("control_mean", "control_mean")],
      )}
      <h3>pred_vs_actual</h3>
      {_render_series_table(
        series.get("pred_vs_actual", []),
        [("t", "t"), ("y_actual", "y_actual"), ("y_pred", "y_pred")],
      )}
      <h3>effect_series</h3>
      {_render_series_table(
        series.get("effect_series", []),
        [("t", "t"), ("effect", "effect"), ("cum_effect", "cum_effect")],
      )}
      <p class="muted">注: テーブルは先頭12行のみ表示しています。</p>
    </section>
  </div>
</body>
</html>
"""

