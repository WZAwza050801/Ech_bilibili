// fetch_list_browser.cjs — 拦截 space 页面自己的 arc/search 响应 + 滚动触发加载
const { chromium } = require('playwright-core');
const fs = require('fs');
const path = require('path');

const MID = 694125286;
const OUT = path.join(__dirname, 'video_list.json');

(async () => {
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
  let totalCount = -1;
  page.on('response', async (resp) => {
    if (!resp.url().includes('arc/search')) return;
    try {
      const j = await resp.json();
      if (j.code !== 0) { console.log('[resp] arc/search code:', j.code, j.message); return; }
      totalCount = j.data.page.count;
      for (const v of j.data.list.vlist) collected.set(v.bvid, { bvid: v.bvid, title: v.title, length: v.length, created: v.created, aid: v.aid });
      console.log(`[resp] +${j.data.list.vlist.length} → 总 ${collected.size}/${totalCount}`);
    } catch (e) { /* 非 JSON 响应（412 页）忽略 */ }
  });

  console.log('[b] goto...');
  await page.goto(`https://space.bilibili.com/${MID}/upload/video`, { waitUntil: 'domcontentloaded', timeout: 45000 });

  // 滚动触发分页加载，直到拿满或超时
  const t0 = Date.now();
  let lastN = -1, stall = 0;
  while (collected.size < totalCount || totalCount < 0) {
    await page.mouse.wheel(0, 3000);
    await page.waitForTimeout(2500);
    if (collected.size === lastN) { stall++; if (stall >= 8) { console.log('[b] 连续8轮无新增，停'); break; } }
    else { stall = 0; lastN = collected.size; }
    if (Date.now() - t0 > 300000) { console.log('[b] 5分钟超时，停'); break; }
    if (totalCount > 0 && collected.size >= totalCount) break;
  }

  const videos = [...collected.values()];
  if (!videos.length) { console.log('[b] FAILED: 一个都没拿到'); await browser.close(); process.exit(2); }
  fs.writeFileSync(OUT, JSON.stringify(videos, null, 1), 'utf-8');
  console.log(`[b] DONE: ${videos.length} 个视频 (total=${totalCount}) -> ${OUT}`);
  await browser.close();
})().catch(e => { console.error('[b] ERROR:', e.message); process.exit(1); });
