from __future__ import annotations

from io import StringIO

import pandas as pd

from .errors import AnalysisError


def csv_to_dataframe(csv_text: str) -> pd.DataFrame:
    if not csv_text.strip():
        raise AnalysisError(
            "CSVが空です。",
            [
                "CSVデータが入力されていません。",
                "ヘッダーとデータ行を含むCSVテキストを送信してください。",
            ],
        )

    try:
        df = pd.read_csv(StringIO(csv_text))
    except Exception as exc:
        raise AnalysisError(
            "CSVを読み込めませんでした。",
            [
                "CSVの区切り文字や引用符が壊れている可能性があります。",
                f"パーサーエラー: {exc}",
            ],
        ) from exc

    df.columns = [str(col).strip() for col in df.columns]

    if df.empty:
        raise AnalysisError(
            "CSVにデータ行がありません。",
            [
                "ヘッダーだけのCSVになっています。",
                "少なくとも1行以上の観測データを入れてください。",
            ],
        )

    return df

