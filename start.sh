#!/bin/bash
set -e

cd "$(dirname "$0")"

# .envがなければ.env.exampleからコピー
if [ ! -f .env ]; then
  cp .env.example .env
  echo ".envファイルを作成しました。認証情報を設定してください。"
fi

cd backend

# 仮想環境を作成してパッケージをインストール
if [ ! -d .venv ]; then
  echo "仮想環境を作成中..."
  python3 -m venv .venv
fi

source .venv/bin/activate

echo "依存パッケージをインストール中..."
pip install -q -r requirements.txt

# Playwright ブラウザをインストール
echo "Playwright ブラウザをインストール中..."
playwright install chromium --with-deps 2>/dev/null || playwright install chromium

echo ""
echo "======================================"
echo "  個人予算管理システム 起動中..."
echo "  http://localhost:8000 でアクセス"
echo "======================================"
echo ""

uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
