# Social Link AI — frontend

Next.js 16 (App Router)。本番は Cloudflare Workers（OpenNext経由）にデプロイしている。全体像は [プロジェクトルートのREADME](../README.md) を参照。

## 開発

```bash
npm install
cp .env.example .env.local   # NEXT_PUBLIC_API_BASE_URL 等を設定
npm run dev                  # http://localhost:3000
```

バックエンド（`../backend`）が別途起動している必要がある。

## Lint / ビルド

```bash
npm run lint
npm run build
```

## Cloudflare Workersへのデプロイ

```bash
NEXT_PUBLIC_API_BASE_URL=https://social-link-ai-backend.fly.dev npx opennextjs-cloudflare build
npx wrangler deploy
```

`NEXT_PUBLIC_API_BASE_URL` はビルド時にクライアントバンドルへ埋め込まれる（実行時ではない）ため、ビルド前に本番バックエンドのURLを指定する必要がある。
