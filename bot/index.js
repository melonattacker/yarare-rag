import express from "express";
import rateLimit from "express-rate-limit";

import { visit, APP_URL } from "./bot.js";

const PORT = "1337";

const app = express();
app.use(express.json());

app.use(express.static("public"));

app.get("/app-url", async (req, res) => {
  return res.send(APP_URL);
});

app.use(
  "/api",
  rateLimit({
    // 各IPにつき1分あたり最大3リクエスト
    windowMs: 60 * 1000,
    max: 3,
  })
);

app.post("/api/report", async (req, res) => {
  const { url } = req.body;

  // /memo/search 以降の相対パスのみ受け付ける
  if (typeof url !== "string" || !url.startsWith("/memo/search")) {
    return res.status(400).send("Invalid url");
  }

  try {
    // 絶対URLに変換してvisit()を実行
    const target = new URL(url, APP_URL).toString();
    await visit(target);
    return res.sendStatus(200);
  } catch (e) {
    console.error(e);
    return res.status(500).send("Something wrong");
  }
});

app.listen(PORT);
