"use client";

import type { ChangeEvent } from "react";
import { useMemo, useState } from "react";
import Papa from "papaparse";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";
import { analyzeCsv, fetchReportHtml } from "../lib/api";
import type { AnalyzeRequestInput, AnalyzeResponse } from "../lib/schemas";

type TabKey = "results" | "diagnostics" | "report";
type FormState = Omit<AnalyzeRequestInput, "csv">;

const INITIAL_FORM: FormState = {
  unit_col: "",
  time_col: "",
  y_col: "",
  treated_col: "",
  policy_start: "2025-03-03"
};

const COLUMN_FIELDS: { key: keyof FormState; label: string }[] = [
  { key: "unit_col", label: "unit列" },
  { key: "time_col", label: "time列" },
  { key: "y_col", label: "y列" },
  { key: "treated_col", label: "treated列" }
];

function guessColumn(headers: string[], hints: string[]): string {
  const normalized = headers.map((value) => value.trim().toLowerCase());
  for (const hint of hints) {
    const idx = normalized.indexOf(hint.toLowerCase());
    if (idx >= 0) {
      return headers[idx];
    }
  }
  for (const hint of hints) {
    const idx = normalized.findIndex((value) => value.includes(hint.toLowerCase()));
    if (idx >= 0) {
      return headers[idx];
    }
  }
  return headers[0] ?? "";
}

function guessForm(headers: string[]): FormState {
  return {
    unit_col: guessColumn(headers, ["unit", "store", "shop", "id"]),
    time_col: guessColumn(headers, ["time", "date", "week"]),
    y_col: guessColumn(headers, ["y", "sales", "outcome", "metric"]),
    treated_col: guessColumn(headers, ["treated", "treatment", "group"]),
    policy_start: "2025-03-03"
  };
}

function formatNumber(value: number, digits = 3): string {
  if (!Number.isFinite(value)) {
    return "-";
  }
  return value.toFixed(digits);
}

function parseErrorMessage(message: string): { title: string; details: string[] } {
  const lines = message
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (lines.length === 0) {
    return {
      title: "エラーが発生しました。",
      details: []
    };
  }
  return {
    title: lines[0],
    details: lines.slice(1)
  };
}

export default function HomePage() {
  const [csvText, setCsvText] = useState("");
  const [headers, setHeaders] = useState<string[]>([]);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("results");
  const [loading, setLoading] = useState(false);
  const [uploadedFileName, setUploadedFileName] = useState("");
  const [errorTitle, setErrorTitle] = useState("");
  const [errorDetails, setErrorDetails] = useState<string[]>([]);

  const kpis = useMemo(() => {
    if (!result) {
      return [];
    }
    return [
      { label: "ATE", value: formatNumber(result.did.ate, 4) },
      {
        label: "95% CI",
        value: `${formatNumber(result.did.ci_low, 4)} ~ ${formatNumber(result.did.ci_high, 4)}`
      },
      { label: "p値", value: formatNumber(result.did.p_value, 6) },
      { label: "観測数 n_obs", value: formatNumber(result.counts.n_obs, 0) }
    ];
  }, [result]);

  async function handleCsvUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }

    const text = await file.text();
    setUploadedFileName(file.name);
    setCsvText(text);
    setResult(null);
    setErrorTitle("");
    setErrorDetails([]);

    const parsed = Papa.parse<Record<string, string>>(text, {
      header: true,
      preview: 1,
      skipEmptyLines: true
    });

    const detectedHeaders = (parsed.meta.fields ?? [])
      .map((value) => value.trim())
      .filter((value) => value.length > 0);

    if (detectedHeaders.length === 0) {
      setHeaders([]);
      setForm(INITIAL_FORM);
      setErrorTitle("CSVヘッダーを取得できませんでした。");
      setErrorDetails(["1行目に列名（例: unit,time,y,treated）を入れてください。"]);
      return;
    }

    setHeaders(detectedHeaders);
    setForm((prev) => ({
      ...guessForm(detectedHeaders),
      policy_start: prev.policy_start || "2025-03-03"
    }));
  }

  function updateField(key: keyof FormState, value: string) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  async function runAnalyze() {
    if (!csvText) {
      setErrorTitle("CSVが未アップロードです。");
      setErrorDetails(["先にCSVファイルを選択してください。"]);
      return;
    }

    for (const field of COLUMN_FIELDS) {
      const value = form[field.key];
      if (!value) {
        setErrorTitle("列設定が不足しています。");
        setErrorDetails([`${field.label}を選択してください。`]);
        return;
      }
    }

    if (!form.policy_start) {
      setErrorTitle("施策開始日が未設定です。");
      setErrorDetails(["policy_startを日付形式で設定してください。"]);
      return;
    }

    setLoading(true);
    setErrorTitle("");
    setErrorDetails([]);

    try {
      const response = await analyzeCsv({
        csv: csvText,
        ...form
      });
      setResult(response);
      setActiveTab("results");
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "API呼び出しでエラーが発生しました。";
      const parsed = parseErrorMessage(message);
      setErrorTitle(parsed.title);
      setErrorDetails(parsed.details);
    } finally {
      setLoading(false);
    }
  }

  async function downloadReport() {
    if (!result?.report_token) {
      setErrorTitle("report_token が取得できていません。");
      setErrorDetails(["再度 Analyze を実行してください。"]);
      return;
    }

    try {
      const html = await fetchReportHtml(result.report_token);
      const blob = new Blob([html], { type: "text/html;charset=utf-8" });
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `impactlab_report_${new Date().toISOString().slice(0, 10)}.html`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(url);
    } catch (err) {
      const message =
        err instanceof Error ? err.message : "レポートダウンロードに失敗しました。";
      const parsed = parseErrorMessage(message);
      setErrorTitle(parsed.title);
      setErrorDetails(parsed.details);
    }
  }

  return (
    <main className="page">
      <section className="hero">
        <h1>ImpactLab</h1>
        <p>CSVを読み込み、DIDと時系列反実仮想を同時に実行するデモアプリです。</p>
      </section>

      <section className="panel">
        <h2 className="section-title">1. CSVアップロードと設定</h2>
        <input type="file" accept=".csv,text/csv" onChange={handleCsvUpload} />
        {uploadedFileName && <p className="hint">読み込み済み: {uploadedFileName}</p>}
        {!uploadedFileName && (
          <p className="hint">
            <code>sample_data/sample.csv</code> をそのまま使えます。
          </p>
        )}

        <div className="form-grid">
          {COLUMN_FIELDS.map((field) => (
            <div className="field" key={field.key}>
              <label>{field.label}</label>
              <select
                value={form[field.key]}
                onChange={(event) => updateField(field.key, event.target.value)}
                disabled={headers.length === 0}
              >
                <option value="">選択してください</option>
                {headers.map((header) => (
                  <option key={header} value={header}>
                    {header}
                  </option>
                ))}
              </select>
            </div>
          ))}

          <div className="field">
            <label>施策開始日 policy_start</label>
            <input
              type="date"
              value={form.policy_start}
              onChange={(event) => updateField("policy_start", event.target.value)}
            />
          </div>
        </div>

        <div className="action-row">
          <button className="primary-btn" onClick={runAnalyze} disabled={loading}>
            {loading ? "分析中..." : "Analyze"}
          </button>
        </div>
      </section>

      {errorTitle && (
        <section className="error-box">
          <strong>{errorTitle}</strong>
          {errorDetails.length > 0 && (
            <ul>
              {errorDetails.map((detail) => (
                <li key={detail}>{detail}</li>
              ))}
            </ul>
          )}
        </section>
      )}

      {result && (
        <>
          <section className="kpi-grid">
            {kpis.map((kpi) => (
              <article className="kpi-card" key={kpi.label}>
                <div className="kpi-label">{kpi.label}</div>
                <div className="kpi-value">{kpi.value}</div>
              </article>
            ))}
          </section>

          <section className="tabs panel">
            <div className="tab-buttons">
              <button
                className={`tab-btn ${activeTab === "results" ? "active" : ""}`}
                onClick={() => setActiveTab("results")}
              >
                結果
              </button>
              <button
                className={`tab-btn ${activeTab === "diagnostics" ? "active" : ""}`}
                onClick={() => setActiveTab("diagnostics")}
              >
                診断
              </button>
              <button
                className={`tab-btn ${activeTab === "report" ? "active" : ""}`}
                onClick={() => setActiveTab("report")}
              >
                レポート
              </button>
            </div>

            {activeTab === "results" && (
              <div className="chart-grid">
                <article className="chart-card">
                  <h3>group_means (treated vs control)</h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={result.series.group_means}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="t" minTickGap={28} />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="treated_mean"
                        stroke="#0f766e"
                        dot={false}
                        strokeWidth={2}
                        name="treated_mean"
                      />
                      <Line
                        type="monotone"
                        dataKey="control_mean"
                        stroke="#334155"
                        dot={false}
                        strokeWidth={2}
                        name="control_mean"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </article>

                <article className="chart-card">
                  <h3>pred_vs_actual (treated group)</h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={result.series.pred_vs_actual}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="t" minTickGap={28} />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="y_actual"
                        stroke="#1d4ed8"
                        dot={false}
                        strokeWidth={2}
                        name="actual"
                      />
                      <Line
                        type="monotone"
                        dataKey="y_pred"
                        stroke="#0ea5e9"
                        dot={false}
                        strokeWidth={2}
                        name="counterfactual_pred"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </article>

                <article className="chart-card">
                  <h3>effect_series (effect & cumulative effect)</h3>
                  <ResponsiveContainer width="100%" height={280}>
                    <LineChart data={result.series.effect_series}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="t" minTickGap={28} />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <Line
                        type="monotone"
                        dataKey="effect"
                        stroke="#b45309"
                        dot={false}
                        strokeWidth={2}
                        name="effect"
                      />
                      <Line
                        type="monotone"
                        dataKey="cum_effect"
                        stroke="#be185d"
                        dot={false}
                        strokeWidth={2}
                        name="cum_effect"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </article>
              </div>
            )}

            {activeTab === "diagnostics" && (
              <div className="diagnostics">
                <article className="chart-card">
                  <h3>平行トレンド診断</h3>
                  <p>
                    <span
                      className={`badge ${
                        result.diagnostics.pretrend_flag === "warn" ? "warn" : ""
                      }`}
                    >
                      {result.diagnostics.pretrend_flag}
                    </span>
                  </p>
                </article>

                <article className="chart-card">
                  <h3>メッセージ</h3>
                  {result.diagnostics.messages.length === 0 ? (
                    <p>診断メッセージはありません。</p>
                  ) : (
                    <ul>
                      {result.diagnostics.messages.map((message) => (
                        <li key={message}>{message}</li>
                      ))}
                    </ul>
                  )}
                </article>

                <article className="chart-card">
                  <h3>欠損率・データ量</h3>
                  <table className="kv-table">
                    <tbody>
                      {Object.entries(result.diagnostics.missing_rates).map(
                        ([column, rate]) => (
                          <tr key={column}>
                            <th>{column}</th>
                            <td>{formatNumber(rate, 2)}%</td>
                          </tr>
                        )
                      )}
                      <tr>
                        <th>outlier_count</th>
                        <td>{result.diagnostics.outlier_count}</td>
                      </tr>
                      <tr>
                        <th>pre_periods</th>
                        <td>{result.diagnostics.pre_periods}</td>
                      </tr>
                      <tr>
                        <th>post_periods</th>
                        <td>{result.diagnostics.post_periods}</td>
                      </tr>
                    </tbody>
                  </table>
                </article>
              </div>
            )}

            {activeTab === "report" && (
              <div className="chart-card">
                <h3>HTMLレポート</h3>
                <p>分析結果からHTMLレポートを生成してダウンロードします。</p>
                <button
                  className="secondary-btn"
                  onClick={downloadReport}
                  disabled={!result.report_token}
                >
                  レポートをダウンロード
                </button>
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
