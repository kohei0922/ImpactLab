# ImpactLab

ブラウザでCSVをアップロードし、以下を一気通貫で実行するデモです。

- DID（差分の差分）による施策効果推定
- 時系列反実仮想（施策前学習→施策後予測）
- 診断（欠損率、データ不足、平行トレンド注意）
- HTMLレポート生成・ダウンロード

## 構成

```text
ImpactLab/
  frontend/      # Next.js (App Router, TypeScript, Zod, Recharts)
  backend/       # FastAPI, pandas, numpy, statsmodels
  sample_data/   # sample.csv, ohtani_dodgers_campaign.csv
  README.md
  package.json   # concurrentlyで frontend+backend 同時起動
```

## セットアップ（Windows）

前提:

- Python 3.11+
- Node.js 20+

手順（プロジェクトルートで実行）:

```powershell
npm install
npm run setup:backend
```

起動:

```powershell
npm run dev
```

起動後:

- Frontend: `http://localhost:3000`
- Backend: `http://localhost:8000`

## 1コマンド起動

開発時の起動は常に以下のみです。

```powershell
npm run dev
```

`concurrently` で frontend と backend を同時に起動します。

## サンプルでの動かし方

1. `http://localhost:3000` を開く
2. `sample_data/sample.csv` または `sample_data/ohtani_dodgers_campaign.csv` をアップロード
3. 列設定（unit/time/y/treated）を確認
4. 施策開始日を設定
   - `sample.csv` の場合: `2025-03-03`
   - `ohtani_dodgers_campaign.csv` の場合: `2023-12-11`
5. `Analyze` を押す
6. 結果タブ/診断タブを確認
7. レポートタブで HTML をダウンロード

### 話題性サンプル（おすすめ）

`sample_data/ohtani_dodgers_campaign.csv`

- 想定ストーリー: 大谷翔平選手のドジャース移籍発表を起点に、MLB関連キャンペーンを実施
- 粒度: 週次パネル（12店舗 × 104週）
- 列: `unit,time,y,treated`
- 推奨 `policy_start`: `2023-12-11`
- 期待される挙動:
  - treated群（sports店舗）で施策後に平均売上が上振れ
  - DIDで正のATE
  - 反実仮想とのギャップが施策後に拡大

## データ仕様

`POST /analyze` の入力:

```json
{
  "csv": "<CSV文字列>",
  "unit_col": "unit",
  "time_col": "time",
  "y_col": "y",
  "treated_col": "treated",
  "policy_start": "2025-03-03"
}
```

必須条件:

- `unit`: ユニット識別子
- `time`: 日付（`YYYY-MM-DD` 推奨）
- `y`: 数値
- `treated`: 0/1（または true/false, yes/no, treated/control）
- 週次データを推奨（診断でチェック）

## API概要

### `POST /analyze`

主な出力:

- `did`: `ate`, `ci_low`, `ci_high`, `p_value`
- `counts`: 観測数、unit数、treated/control unit数
- `series`:
  - `group_means`
  - `pred_vs_actual`
  - `effect_series`
- `diagnostics`: `pretrend_flag`, `messages`, 欠損率など
- `report_token`: レポート取得用トークン

### `GET /report?token=...`

直前の分析結果に基づいたHTMLレポートを返します。

### `POST /report`

`token` または `config + analysis` を渡してHTMLレポートを返します。

### `GET /summarize/status`

AI要約が利用可能かを返します。`OPENAI_API_KEY` 未設定時は `enabled=false` です。

### `POST /summarize`

分析結果JSONをOpenAI APIに渡し、以下を返します。

- `summary`: 全体要約
- `warnings`: 解釈上の注意点
- `next_steps`: 次アクション

環境変数:

- `OPENAI_API_KEY` (必須)
- `OPENAI_MODEL` (任意、既定: `gpt-4.1-mini`)

## 設計メモ

バックエンドは責務ごとに分割しています。

- `backend/src/parse.py`: CSV文字列→DataFrame
- `backend/src/validate.py`: 列検証、型変換、診断ロジック
- `backend/src/transform.py`: post列生成、集計
- `backend/src/analyze_did.py`: DID回帰
- `backend/src/analyze_ts.py`: 施策前学習の反実仮想予測
- `backend/src/report.py`: HTMLレポート生成
- `backend/main.py`: FastAPIエントリ

## ログ

バックエンドは以下の処理時間をログ出力します。

- parse
- validate
- transform
- did
- ts_counterfactual
- report

## 限界（重要）

- DIDは平行トレンド仮定に依存します（診断はヒューリスティック）。
- 本実装の時系列モデルはシンプルな線形回帰（trend + seasonality dummies）です。
- 因果推論の厳密性はデータ設計に強く依存します。
- 外れ値処理はIQRベースの簡易判定です。

## スクリーンショット

任意。必要であれば `docs/` 配下に画像を追加してください。
