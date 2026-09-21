# -*- coding: utf-8 -*-
"""rank_lex.py — 用 LLM 给 Lex 播客嘉宾知名度打分, 生成大佬优先的跑批队列
输入: lex_episodes.json  输出: lex_queue.json (按 fame 降序)
"""
import json, io, sys, re, time
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
WORK = Path(r"D:\视频观看agent编写\Ech_youtube")

secrets = json.load(open(r"D:\密码书\private\private-ai-api-secrets.json", encoding="utf-8"))
_entry = next(e for e in secrets["entries"] if e.get("label") == "Environment DEEPSEEK_API_KEY")
API_KEY, BASE_URL, MODEL = _entry["apiKey"], (_entry.get("baseUrl") or "https://api.deepseek.com").rstrip("/"), "deepseek-chat"

import urllib.request
def call_llm(system, user, temp=0.1, retry=3):
    body = json.dumps({"model": MODEL, "temperature": temp, "stream": False,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode("utf-8")
    last = None
    for i in range(retry):
        try:
            req = urllib.request.Request(f"{BASE_URL}/chat/completions", data=body,
                                         headers={"Authorization": f"Bearer {API_KEY}",
                                                  "Content-Type": "application/json"})
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            return json.loads(opener.open(req, timeout=300).read().decode("utf-8"))["choices"][0]["message"]["content"].strip()
        except Exception as e:
            last = e; time.sleep(5 * (i + 1))
    raise RuntimeError(f"LLM: {last}")

SYS = ("你在给播客嘉宾的公众知名度打分(0-10)。10=全球家喻户晓(国家元首、马斯克级别的科技领袖、"
       "诺奖/菲尔兹奖级学者、全球顶级运动员/艺人)；7-9=业内极有名或公众熟度高；4-6=业内知名；"
       "1-3=小众。对每行输入 `[序号] 嘉宾名` 输出 `[序号] 分数`，一行一个，不要解释。")

data = json.loads((WORK / "lex_episodes.json").read_text(encoding="utf-8"))
entries = data["entries"]

def parse_title(t):
    m = re.search(r"#(\d+)", t)
    num = int(m.group(1)) if m else 0
    guest = t.split(":")[0].strip() if ":" in t else t.split("|")[0].strip()
    return num, guest

seen, items = set(), []
for e in entries:
    num, guest = parse_title(e["title"])
    if not num or guest.lower() in ("lex fridman", "lex"):
        continue
    if e["vid"] in seen:
        continue
    seen.add(e["vid"])
    items.append({"vid": e["vid"], "num": num, "guest": guest, "title": e["title"]})
print(f"解析出 {len(items)} 期访谈")

# LLM 打分(缓存文件支持断点)
score_f = WORK / "lex_fame_scores.json"
scores = json.loads(score_f.read_text(encoding="utf-8")) if score_f.exists() else {}
todo = [it for it in items if it["guest"] not in scores]
print(f"待打分 {len(todo)} 个嘉宾")
for bi in range(0, len(todo), 60):
    batch = todo[bi:bi + 60]
    numbered = "\n".join(f"[{i}] {p['guest']}" for i, p in enumerate(batch))
    out = call_llm(SYS, numbered)
    got = {}
    for line in out.splitlines():
        m = re.match(r"^\[(\d+)\]\s*(\d+)", line.strip())
        if m:
            got[int(m.group(1))] = int(m.group(2))
    for i, p in enumerate(batch):
        scores[p["guest"]] = got.get(i, 3)
    (score_f).write_text(json.dumps(scores, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"打分进度 {min(bi+60, len(todo))}/{len(todo)}")

for p in items:
    p["fame"] = scores.get(p["guest"], 3)
items.sort(key=lambda p: (-p["fame"], p["num"]))
(WORK / "lex_queue.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
top = [f"{p['num']}-{p['guest']}({p['fame']})" for p in items[:15]]
print("TOP15:", " | ".join(top))
