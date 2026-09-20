// fetch_list_retry.cjs — 低强度冷却重试：拦截 space 页面自然请求拉视频列表
// 每轮: 冷启动浏览器 → 打开页面 → 监听 arc/search + 滚动 90s → 成功则保存
// 失败: 等 180s 冷却，最多 6 轮
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const MID = 694125286;
const OUT = path.join(__dirname, 'video_list.json');
const MAX_ROUNDS = 6;

const sleep = ms => new Promise(res => setTimeout(res, ms));

async function tryOnce(round) {
  const browser = await chromium.launch({
    channel: 'msedge',
    headless: false,
    args: ['--disable-blink-features=AutomationControlled', '--no-proxy-server'],
  });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();
  const collected = new Map();
  let totalCount = -1, hitCount = 0;
  page.on('response', async (resp) => {
    if (!resp.url().includes('arc/search')) return;
    hitCount++;
    try {
      const j = await resp.json();
      if (j.code !== 0) { console.log(`[r${round}] arc/search code:`, j.code, j.message); return; }
      totalCount = j.data.page.count;
      for (const v of j.data.list.vlist) collected.set(v.bvid, { bvid: v.bvid, title: v.title, length: v.length, created: v.created, aid: v.aid });
      console.log(`[r${round}] +${j.data.list.vlist.length} → ${collected.size}/${totalCount}`);
    } catch (e) { console.log(`[r${round}] arc/search 非JSON(412?)`); }
  });

  try {
    await page.goto(`https://space.bilibili.com/${MID}/upload/video`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(6000);
    const t0 = Date.now();
    let lastN = -1, stall = 0;
    while (Date.now() - t0 < 120000) {
      await page.mouse.wheel(0, 3000);
      await sleep(2500);
      if (totalCount > 0 && collected.size >= totalCount) break;
      if (collected.size === lastN) { if (++stall >= 6) break; } else { stall = 0; lastN = collected.size; }
    }
  } finally {
    await browser.close().catch(() => {});
  }
  return { videos: [...collected.values()], totalCount, hitCount };
}

(async () => {
  for (let round = 1; round <= MAX_ROUNDS; round++) {
    console.log(`[main] === 第 ${round}/${MAX_ROUNDS} 轮 ===`);
    const { videos, totalCount } = await tryOnce(round);
    if (videos.length && (totalCount < 0 || videos.length >= totalCount)) {
      fs.writeFileSync(OUT, JSON.stringify(videos, null, 1), 'utf-8');
      console.log(`[main] DONE: ${videos.length} (total=${totalCount}) -> ${OUT}`);
      process.exit(0);
    }
    if (round < MAX_ROUNDS) {
      console.log(`[main] 本轮失败(${videos.length}个)，冷却 180s...`);
      await sleep(180000);
    }
  }
  console.log('[main] FAILED: 全部轮次用尽');
  process.exit(2);
})();
