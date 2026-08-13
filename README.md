# Social Link AI

ASD等コミュニケーションに難がある人向けの、対面での会話を録音・分析して対話を支援するWebアプリケーション。会話を録音→停止→解析し、話題・会話の流れ・相手の反応・関係性の距離感をレポートとして提示する。場面（職場・学校・初対面・友人・恋愛）ごとに視点を変えたフィードバックを行う。発言前にテキストで下書きをチェックする機能や、会話後の振り返り記録も持つ。

詳細な要件・設計判断の経緯は [docs/requirements/requirements-definition.md](docs/requirements/requirements-definition.md) を参照。

## アーキテクチャ

```
frontend/  Next.js 16 (App Router)         → Cloudflare Workers（OpenNext経由）
backend/   FastAPI + Celery                → Fly.io（api / worker / beat の3プロセス）
                                              DB: Supabase (Postgres)
                                              ブローカー/一時保管: Upstash Redis（Fly連携）
```

フロントエンドとバックエンドは別ドメイン・別インフラで動作する。認証はBearerアクセストークン＋リフレッシュトークン（httpOnly cookie、バックエンド自身のオリジンにのみスコープ）方式で、クロスオリジン構成でも機能する。

### 音声解析パイプライン（3層構成）

1. **STT**（AmiVoice ESAS）— 音声認識・話者分離・プロソディ（感情）分析を1コールで実施
2. **話者識別** — 登録済み声紋（SpeechBrain ECAPA-TDNN、話者埋め込みのコサイン類似度）で「自分」「相手」を判定
3. **LLM統合層**（Claude API）— テキスト・感情スコア・場面プリセットを統合し、レポート・提案を生成

## リポジトリ構成

```
backend/    FastAPI アプリケーション本体
  app/
    api/            エンドポイント
    services/       ビジネスロジック
    integrations/   外部ベンダー（STT/LLM/メール/話者識別）のアダプタ
    workers/        Celeryタスク（解析パイプライン・定期クリーンアップ）
    models/ repositories/ schemas/
  tests/
  fly.toml          Fly.ioデプロイ設定
  Dockerfile

frontend/   Next.js アプリケーション本体
  app/
    (authed)/       要ログインのページ群
    (guest)/        未ログイン専用のページ群（ログイン・登録等）
  components/ lib/ hooks/
  wrangler.jsonc    Cloudflare Workersデプロイ設定
  open-next.config.ts

infra/
  docker-compose.yml   ローカル開発用（postgres・redis・api・worker・beat）

docs/
  requirements/requirements-definition.md   要件定義・設計判断の記録
  依頼者に確認していただきたいこと.txt        依頼主向けの現状報告・引き継ぎ資料
```

## ローカル開発

### 前提

- Docker（推奨）、または Python 3.11+ / Node.js 22+ を直接インストール
- `uv`（Pythonパッケージ管理）、`npm`

### 環境変数

```bash
cp .env.keys.example .env.keys        # 外部ベンダーAPIキー（プロジェクト直下）
cp backend/.env.example backend/.env  # バックエンド設定
cp frontend/.env.example frontend/.env.local  # フロントエンド設定（存在する場合）
```

`.env.keys` に Anthropic・AmiVoice・Resend 等のAPIキーを記入する。詳細は各ファイルのコメントを参照。

### Docker Composeで起動（推奨）

```bash
docker compose -f infra/docker-compose.yml up
```

postgres・redis・api（`:8000`）・worker・beat が一括で起動する。

### 個別に起動する場合

```bash
# バックエンド
cd backend
uv sync --extra speaker-id   # speaker-id extraはPyTorch等を含み重いが、ecapa_local使用時は必須
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

# 別ターミナルでCeleryワーカー
uv run celery -A app.core.celery_app worker --loglevel=info

# フロントエンド
cd frontend
npm install
npm run dev   # http://localhost:3000
```

### テスト・Lint

```bash
# バックエンド
cd backend
uv run ruff check app/ tests/
uv run pytest tests/ -v

# フロントエンド
cd frontend
npm run lint
npm run build
```

## デプロイ

- **フロントエンド**: `cd frontend && npx opennextjs-cloudflare build && npx wrangler deploy`
- **バックエンド**: `cd backend && flyctl deploy --app social-link-ai-backend`（`fly.toml`の`release_command`でマイグレーションも自動実行）

本番運用に向けて対応が必要な項目（APIキーの本番差し替え、レート制限、利用規約の法務レビュー等）は [docs/依頼者に確認していただきたいこと.txt](docs/依頼者に確認していただきたいこと.txt) にまとめてある。
