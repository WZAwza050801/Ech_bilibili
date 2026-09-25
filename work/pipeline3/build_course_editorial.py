"""Chief-editor stage: merge per-page analyses into one coherent course volume.

Model chain: kimi-code k3-256k (Anthropic protocol) ->
openrouter moonshotai/kimi-k3 (OpenAI protocol, direct then via proxy) ->
deepseek-chat. The editor may reorganize wording, unify terminology, add a
global learning path, and surface contradictions -- but never invent facts,
timestamps, or steps that are not in the input.
"""
import json
import urllib.request
from pathlib import Path


def _post(url, body, headers, timeout=600):
    request = urllib.request.Request(
        url, data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read())


def anthropic_text(base, key, model, system, user, max_tokens=32000):
    payload = _post(base.rstrip("/") + "/messages", {
        "model": model, "max_tokens": max_tokens, "system": system,
        "messages": [{"role": "user", "content": user}]},
        {"x-api-key": key, "anthropic-version": "2023-06-01",
         "Content-Type": "application/json"})
    return "".join(b.get("text", "") for b in payload.get("content", [])
                   if b.get("type") == "text")


def openai_text(base, key, model, system, user, proxy=None, max_tokens=32000):
    body = {"model": model, "max_tokens": max_tokens, "messages": [
        {"role": "system", "content": system}, {"role": "user", "content": user}]}
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json"}
    if proxy:
        opener = urllib.request.build_opener(urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy}))
        request = urllib.request.Request(
            base.rstrip("/") + "/chat/completions",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers, method="POST")
        with opener.open(request, timeout=900) as response:
            payload = json.loads(response.read())
    else:
        payload = _post(base.rstrip("/") + "/chat/completions", body, headers, timeout=900)
    return payload["choices"][0]["message"]["content"]


def digest_page(run_dir, entry):
    analysis = json.loads((run_dir / "analysis.json").read_text(encoding="utf-8"))
    execution = []
    exec_path = run_dir / "execution.json"
    if exec_path.exists():
        execution = json.loads(exec_path.read_text(encoding="utf-8")).get("records", [])
    status = {x.get("id"): x.get("status") for x in execution}
    steps = [{
        "id": s.get("id"), "title": s.get("title"), "action": s.get("action"),
        "path": s.get("path"), "expected": s.get("expected"),
        "details": s.get("details"), "evidence_t": s.get("evidence_t"),
        "status": status.get(s.get("id"), "n/a"),
    } for s in analysis.get("steps", [])]
    return {
        "page": entry.get("page"), "title": entry.get("title"),
        "duration_s": entry.get("duration_s"),
        "url": entry.get("url"), "grade": analysis.get("classification"),
        "summary": analysis.get("summary"),
        "sections": analysis.get("sections"),
        "concepts": analysis.get("concepts"),
        "steps": steps, "gaps": analysis.get("gaps"),
        "tutorial_issues": analysis.get("tutorial_issues"),
    }


EDITOR_SYSTEM = """你是《课程总讲义》总编辑。输入是一部多分P课程的全部分P结构化分析（含步骤、执行验证结果、已知缺口）。
你的任务是把分P素材整合成一部连贯的中文总讲义，规则：
1. 开篇写"全局学习路径"：课程整体脉络、建议学习顺序、各P之间的依赖关系。
2. 建立"术语与符号统一表"：合并各P重复概念，统一译名与写法。
3. 之后每个P一节。只调整行文与衔接，绝不改动事实：步骤编号、时间戳、参数值、执行状态必须原样保留。
4. 跨P重复出现的内容在后续章节改为"见 Px 第 n 步"式交叉引用，不要重抄。
5. 发现各P之间矛盾或不一致时，单列"矛盾与存疑"一节，逐条列出双方出处，不要自行裁决。
6. 末尾汇总全部 gaps 与 tutorial_issues 为"已知缺口与注意事项"一章。
7. 禁止发明任何输入中没有的内容；禁止删除任何步骤；禁止修改任何时间戳。
输出：直接输出 Markdown 正文，不要包裹代码块，不要任何解释。"""


def build(course_dir, deepseek_key=None, proxy="http://127.0.0.1:12000"):
    index_path = course_dir / "course-index.json"
    entries = [e for e in json.loads(index_path.read_text(encoding="utf-8"))
               # ok=False pages may still have a complete analysis (e.g. the
               # evidence-frames stage OOMed after analysis was saved).
               if e.get("ok") or (course_dir / e["run_dir"] / "analysis.json").exists()]
    if not entries:
        raise RuntimeError("no completed pages to edit")
    entries.sort(key=lambda e: e.get("page", 0))
    pages = [digest_page(course_dir / e["run_dir"], e) for e in entries]
    user_text = ("课程分P分析素材（JSON）：\n\n" +
                 json.dumps(pages, ensure_ascii=False, indent=1))
    attempts = []
    # 1. kimi-code k3-256k (Anthropic protocol, domestic, no proxy)
    kc = _secret("kimi-code")
    if kc:
        base = (kc.get("baseUrl") or "https://api.kimi.com/coding/v1").rstrip("/")
        try:
            text = anthropic_text(base, kc["apiKey"], "k3-256k", EDITOR_SYSTEM, user_text)
            return text, "kimi-code/k3-256k", attempts
        except Exception as exc:
            attempts.append(f"k3-256k: {type(exc).__name__} {str(exc)[:150]}")
    # 2. openrouter kimi-k3 (direct, then via proxy)
    orr = _secret("openrouter")
    if orr:
        base = (orr.get("baseUrl") or "https://openrouter.ai/api/v1").rstrip("/")
        for label, use_proxy in (("direct", None), ("proxy", proxy)):
            try:
                text = openai_text(base, orr["apiKey"], "moonshotai/kimi-k3",
                                   EDITOR_SYSTEM, user_text, proxy=use_proxy)
                return text, f"openrouter/kimi-k3 ({label})", attempts
            except Exception as exc:
                attempts.append(f"kimi-k3/{label}: {type(exc).__name__} {str(exc)[:150]}")
    # 3. aliyun token-plan (OpenAI protocol, domestic, subscription quota)
    tp = _secret_tokenplan()
    if tp:
        for model in ("qwen3.8-max", "deepseek-v4-pro"):
            try:
                text = openai_text(tp["baseUrl"].rstrip("/"), tp["apiKey"], model,
                                   EDITOR_SYSTEM, user_text)
                return text, f"token-plan/{model}", attempts
            except Exception as exc:
                attempts.append(f"token-plan/{model}: {type(exc).__name__} {str(exc)[:150]}")
    # 4. deepseek-chat
    ds = _secret("deepseek")
    if ds:
        base = (ds.get("baseUrl") or "https://api.deepseek.com").rstrip("/")
        if not base.endswith("/v1"):
            base = base + "/v1"
        try:
            text = openai_text(base, ds["apiKey"], "deepseek-chat",
                               EDITOR_SYSTEM, user_text)
            return text, "deepseek/deepseek-chat", attempts
        except Exception as exc:
            attempts.append(f"deepseek: {type(exc).__name__} {str(exc)[:150]}")
    raise RuntimeError("all editor models failed: " + " | ".join(attempts))


def _secret(provider):
    path = Path(r"D:\密码书\private\private-ai-api-secrets.json")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for entry in data.get("entries", []):
        if entry.get("provider") == provider and entry.get("apiKey"):
            return entry
    return None


def _secret_tokenplan():
    """Aliyun Token Plan team key: bailian entries on token-plan.* host with sk-sp- key."""
    path = Path(r"D:\密码书\private\private-ai-api-secrets.json")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    for entry in data.get("entries", []):
        if (entry.get("provider") == "bailian" and entry.get("apiKey", "").startswith("sk-sp-")
                and "token-plan" in (entry.get("baseUrl") or "")):
            return entry
    return None


def main():
    import sys
    candidates = sorted((Path(__file__).resolve().parent / "runs").glob("Godot游戏特效-*/course-index.json"))
    index_path = max(candidates, key=lambda p: p.parent.name)
    course_dir = index_path.parent
    text, model, attempts = build(course_dir)
    out_dir = course_dir / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "课程总讲义.md").write_text(text, encoding="utf-8")
    (out_dir / "editor-meta.json").write_text(json.dumps(
        {"model": model, "attempts": attempts}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    print(json.dumps({"output": str(out_dir / "课程总讲义.md"), "model": model},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
