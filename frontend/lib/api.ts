import {
  AnalyzeRequestSchema,
  AnalyzeResponseSchema,
  ErrorResponseSchema,
  type AnalyzeRequestInput,
  type AnalyzeResponse
} from "./schemas";

const BACKEND_BASE = process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";

function parseErrorPayload(payload: unknown): string {
  const parsed = ErrorResponseSchema.safeParse(payload);
  if (!parsed.success) {
    return "エラー詳細を解釈できませんでした。";
  }
  if (parsed.data.details.length === 0) {
    return parsed.data.message;
  }
  return `${parsed.data.message}\n${parsed.data.details.join("\n")}`;
}

export async function analyzeCsv(input: AnalyzeRequestInput): Promise<AnalyzeResponse> {
  const request = AnalyzeRequestSchema.parse(input);

  const response = await fetch(`${BACKEND_BASE}/analyze`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json"
    },
    body: JSON.stringify(request)
  });

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`APIエラー (${response.status})`);
    }
    throw new Error(parseErrorPayload(payload));
  }

  const data = await response.json();
  return AnalyzeResponseSchema.parse(data);
}

export async function fetchReportHtml(token: string): Promise<string> {
  if (!token) {
    throw new Error("report_token が空です。");
  }

  const response = await fetch(
    `${BACKEND_BASE}/report?token=${encodeURIComponent(token)}`,
    {
      method: "GET"
    }
  );

  if (!response.ok) {
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      throw new Error(`レポート取得に失敗しました (${response.status})`);
    }
    throw new Error(parseErrorPayload(payload));
  }

  return response.text();
}

