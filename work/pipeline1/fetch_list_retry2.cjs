// fetch_list_retry2.cjs — 混合策略：页面自然请求拿第一页，翻页用签名fetch+长间隔退避
const { chromium } = require('playwright-core');
const crypto = require('crypto');
const https = require('https');
const fs = require('fs');
const path = require('path');

const MID = 694125286;
const OUT = path.join(__dirname, 'video_list.json');
const MAX_ROUNDS = 5;
const TAB = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52];

const sleep = ms => new Promise(res => setTimeout(res, ms));

function fetchJSON(url, headers = {}) {
  return new Promise((resolve, reject) => {
    https.get(url, { headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36', ...headers } }, res => {
      let buf = '';
      res.on('data', c => buf += c);
      res.on('end', () => { try { resolve(JSON.parse(buf)); } catch (e) { reject(new Error('non-json ' + res.statusCode)); } });
    }).on('error', reject);
  });
}

async function getWbiKeys() {
  const d = await fetchJSON('https://api.bilibili.com/x/web-interface/nav');
  const w = d.data.wbi_img;
  return [w.img_url.split('/').pop().split('.')[0], w.sub_url.split('/').pop().split('.')[0]];
}

function signedUrl(params, mixin) {
  const q = Object.keys(params).sort().map(k => `${k}=${String(params[k]).replace(/[!'()*]/g, '')}`).join('&');
  const rid = crypto.createHash('md5').update(q + mixin).digest('hex');
  return `https://api.bilibili.com/x/space/wbi/arc/search?${q}&w_rid=${rid}`;
}

async function tryOnce(round, mixin, globalMap) {
  const browser = await chromium.launch({
    channel: 'msedge', headless: false,
    args: ['--disable-blink-features=AutomationControlled', '--no-proxy-server'],
  });
  const ctx = await browser.newContext({
    userAgent: 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0',
    viewport: { width: 1440, height: 900 },
  });
  const page = await ctx.newPage();
  const collected = globalMap;  // 跨轮累积, 直接引用全局 map
  let totalCount = -1;
  const absorb = (j) => {
    totalCount = j.data.page.count;
    let fresh = 0;
    for (const v of j.data.list.vlist) if (!collected.has(v.bvid)) { collected.set(v.bvid, { bvid: v.bvid, title: v.title, length: v.length, created: v.created, aid: v.aid }); fresh++; }
    return fresh;
  };
  page.on('response', async (resp) => {
    if (!resp.url().includes('arc/search')) return;
    try {
      const j = await resp.json();
      if (j.code !== 0) return;
      const fresh = absorb(j);
      console.log(`[r${round}] page-resp +${fresh} → ${collected.size}/${totalCount}`);
    } catch (e) { /* 412 HTML */ }
  });

  try {
    await page.goto(`https://space.bilibili.com/${MID}/upload/video`, { waitUntil: 'domcontentloaded', timeout: 45000 });
    await page.waitForTimeout(10000);   // 等页面自己的第一页请求
    console.log(`[r${round}] 自然请求后: ${collected.size}/${totalCount}`);

    // 翻页: ps=50, pn 从 2 起, 长间隔, 412 退避
    const t0 = Date.now();
    let pn = 2;
    while ((totalCount < 0 || collected.size < totalCount) && Date.now() - t0 < 900000) {
      const url = signedUrl({ mid: MID, ps: 50, pn, order: 'pubdate', platform: 'web', web_location: '1550505', order_avoided: 'true', wts: Math.floor(Date.now() / 1000) }, mixin);
      let ok = false;
      for (let attempt = 0; attempt < 5 && !ok; attempt++) {
        try {
          const r = await page.evaluate(async (u) => {
            const resp = await fetch(u, { credentials: 'include' });
            const txt = await resp.text();
            return txt.startsWith('{') ? JSON.parse(txt) : { code: resp.status, message: 'html' };
          }, url);
          if (r.code === 0) {
            const fresh = absorb(r);
            console.log(`[r${round}] fetch pn${pn}: +${fresh} → ${collected.size}/${totalCount}`);
            if (collected.size >= r.data.page.count) return { totalCount };
            pn++; ok = true;
            await sleep(15000);
          } else {
            console.log(`[r${round}] pn${pn} code=${r.code}, 退避 45s (${attempt + 1}/5)`);
            await sleep(45000);
          }
        } catch (e) { console.log(`[r${round}] pn${pn} err ${e.message}, 退避45s`); await sleep(45000); }
      }
      if (!ok) { pn++; await sleep(20000); }  // 该页彻底失败也继续下一页
      if (totalCount > 0 && collected.size >= totalCount) break;
    }
  } finally {
    await browser.close().catch(() => {});
  }
  return { totalCount };
}

(async () => {
  const [ik, sk] = await getWbiKeys();
  const mixin = TAB.map(i => (ik + sk)[i]).join('').slice(0, 32);
  console.log('[main] wbi keys ok');
  const PARTIAL = path.join(__dirname, 'video_list_partial.json');
  const globalMap = new Map();
  if (fs.existsSync(PARTIAL)) for (const v of JSON.parse(fs.readFileSync(PARTIAL, 'utf-8'))) globalMap.set(v.bvid, v);
  console.log(`[main] 已有累积: ${globalMap.size}`);
  const save = (n) => { fs.writeFileSync(PARTIAL, JSON.stringify([...globalMap.values()], null, 1), 'utf-8'); console.log(`[main] 进度已保存: ${n}`); };

  for (let round = 1; round <= 8; round++) {
    console.log(`[main] === 第 ${round}/8 轮 (已有 ${globalMap.size}) ===`);
    const { totalCount } = await tryOnce(round, mixin, globalMap);
    save(globalMap.size);
    if (globalMap.size > 0 && (totalCount < 0 || globalMap.size >= totalCount)) {
      fs.writeFileSync(OUT, JSON.stringify([...globalMap.values()], null, 1), 'utf-8');
      console.log(`[main] DONE: ${globalMap.size} (total=${totalCount}) -> ${OUT}`);
      process.exit(0);
    }
    console.log('[main] 冷却 180s...');
    await sleep(180000);
  }
  if (globalMap.size) { fs.writeFileSync(OUT, JSON.stringify([...globalMap.values()], null, 1), 'utf-8'); console.log(`[main] 部分完成: ${globalMap.size}`); process.exit(0); }
  console.log('[main] FAILED');
  process.exit(2);
})();
