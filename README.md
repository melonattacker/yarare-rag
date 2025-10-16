# yarare-rag

```
# ソースコードをダウンロード
$ git clone https://github.com/melonattacker/yarare-rag.git
$ cd yarare-rag

# OpenAI APIキーをセット
$ vim .env
OPENAI_API_KEY=sk-xxxx

# アプリを起動
$ docker compose up -d

# アプリの停止（データ削除はしない）
$ docker compose down

# アプリの停止（データ削除含む）
$ docker compose down -v
```