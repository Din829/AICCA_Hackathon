
# AICCA - AI Content Credibility Agent

AIコンテンツの信頼性を検証するReActアーキテクチャベースのエージェントシステム

## 概要

AICCAは、テキスト・画像・動画の真偽判定を行うAIエージェントです。複数の検証ツールを組み合わせて、コンテンツの信頼性を総合的に評価します。

## 技術スタック

- **バックエンド**: Python FastAPI + WebSocket
- **フロントエンド**: Next.js 15 + React 19 + TypeScript
- **AI**: Gemini API + ReActアーキテクチャ
- **検証ツール**: Sightengine、C2PA、Google Vision API

## クイックスタート

### 1. 依存関係のインストール

```bash
# Python依存関係
pip install -r requirements.txt
pip install -r requirements_aicca.txt

# フロントエンド依存関係
cd packages/web
npm install
```

### 2. 環境設定

```bash
# 環境変数ファイルをコピー
cp .env.example .env

# .envファイルを編集してAPIキーを設定
# GOOGLE_API_KEY=your_api_key_here
# SIGHTENGINE_API_USER=your_user_id
# SIGHTENGINE_API_SECRET=your_secret
```

### 3. サーバー起動

```bash
# バックエンド起動 (ポート8000)
python aicca_app.py

# フロントエンド起動 (ポート3000)
cd packages/web
npm run dev
```

### 4. アクセス

- **Webアプリ**: http://localhost:3000
- **API文書**: http://localhost:8000/docs
- **WebSocket**: ws://localhost:8000/ws/chat

## 主要機能

### コンテンツ検証
- **テキスト検証**: AI生成テキストの検出
- **画像検証**: AI生成画像・ディープフェイクの検出
- **C2PA検証**: コンテンツ認証・改ざん検出
- **メタデータ分析**: EXIF情報・技術的異常の検出

### システム特徴
- **リアルタイム分析**: WebSocketによる即座の結果表示
- **多言語対応**: 日本語・英語・中国語
- **モジュラー設計**: 拡張可能なツールアーキテクチャ
- **包括的ログ**: 詳細な分析履歴

## システム要件

- **Python**: 3.9以上
- **Node.js**: 20以上
- **必須APIキー**: Google Gemini API、Sightengine API

## プロジェクト構成

```
AICCA/
├── aicca_app.py              # バックエンドメインエントリ
├── packages/
│   ├── core/                 # コアエンジン
│   │   └── src/aicca/        # AICCA専用ツール
│   ├── api/                  # API拡張
│   └── web/                  # Next.jsフロントエンド
├── requirements.txt          # Python依存関係
└── requirements_aicca.txt    # AICCA専用依存関係
```

## 開発

### バックエンド開発

```bash
# 開発モード起動（自動リロード）
python aicca_app.py

# 特定ポートで起動
uvicorn aicca_app:app --host 0.0.0.0 --port 8000 --reload
```

### フロントエンド開発

```bash
cd packages/web

# 開発サーバー起動
npm run dev

# 型チェック
npm run type-check

# ビルド
npm run build
```

## API仕様

### WebSocket接続

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');
ws.send(JSON.stringify({
  type: 'message',
  content: 'この画像は本物ですか？',
  files: [/* ファイルデータ */]
}));
```

### REST API

```bash
# ヘルスチェック
GET /health

# API情報
GET /api/info

# チャット履歴
GET /api/chat/history
```

## ライセンス

MIT License