// bot.js
import puppeteer from "puppeteer";

const APP_HOST = "web";
const APP_PORT = "33456";
export const APP_URL = `http://${APP_HOST}:${APP_PORT}`;

const SUPER_ADMIN_USER = process.env.SUPER_ADMIN_USER || "super-admin";
const SUPER_ADMIN_PASS = process.env.SUPER_ADMIN_PASS || "dummy_super_admin_pass";

const sleep = async (ms) => new Promise((resolve) => setTimeout(resolve, ms));

export const visit = async (url) => {
  // url は server.js 側で APP_URL を基準に絶対URL化済み（/memo/search?...）
  console.log(`start: ${url}`);

  const browser = await puppeteer.launch({
    headless: "new",
    executablePath: "/usr/bin/chromium",
    args: [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu",
      '--js-flags="--noexpose_wasm"',
    ],
  });

  const context = await browser.createBrowserContext();

  try {
    // 1) super-admin でログイン
    const page = await context.newPage();
    page.setDefaultTimeout(1000);

    // /login を開く
    await page.goto(`${APP_URL}/login`, { timeout: 5_000 });
    await sleep(500);

    // フォーム入力（name="username", name="password"）
    await page.type('input[name="username"]', SUPER_ADMIN_USER, { delay: 10 });
    await page.type('input[name="password"]', SUPER_ADMIN_PASS, { delay: 10 });

    // 送信 → 遷移待ち
    await Promise.all([
      page.click('button[type="submit"], button.btn.btn-primary'),
      page.waitForNavigation({ timeout: 5_000 }).catch(() => {}),
    ]);
    await sleep(500);

    // 2) /memo/search?... を開く
    await page.goto(url, { timeout: 5_000 });

    // 3) 検索ボタンをクリックして POST 実行
    //    （フォームが1つ想定。button[type=submit] か .btn-primary を対象）
    try {
      await page.waitForSelector("form", { timeout: 5000 });
      await Promise.all([
        page.click('form button[type="submit"], form button.btn-primary'),
        page.waitForNavigation({ timeout: 5_000 }).catch(() => {}),
      ]);
    } catch {
      // セレクタが見つからない場合はフォーム直接 submit()
      await page.evaluate(() => {
        const f = document.querySelector("form");
        if (f) f.submit();
      });
      // 送信後のサーバ処理待ち
      await sleep(1_000);
    }

    // 画像読み込みや追加リクエストの発火待ち（間接PI用）
    await sleep(2_000);

    await page.close();
  } catch (e) {
    console.error(e);
  }

  await context.close();
  await browser.close();

  console.log(`end: ${url}`);
};
