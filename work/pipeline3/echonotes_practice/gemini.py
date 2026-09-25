import http.client
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit
from pathlib import Path


def message_part(raw):
    try:
        return json.loads(raw).get("error", {}).get("message", raw)
    except json.JSONDecodeError:
        return raw


def extract_json(text):
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0]
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Model response did not contain a JSON object")
    return json.loads(text[start:end + 1])


def interaction_text(response):
    texts = [item.get("text", "") for item in response.get("outputs", [])
             if item.get("type") == "text"]
    for step in response.get("steps", []):
        if step.get("type") == "model_output":
            texts.extend(item.get("text", "") for item in step.get("content", [])
                         if item.get("type") == "text")
    return "\n".join(x for x in texts if x).strip()


def api_key_from(secrets_path=None):
    if os.getenv("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    if not secrets_path:
        raise RuntimeError("Set GEMINI_API_KEY or pass --secrets")
    data = json.loads(Path(secrets_path).read_text(encoding="utf-8-sig"))
    matches = [x for x in data.get("entries", []) if x.get("provider") == "google-ai"]
    if len(matches) != 1 or not matches[0].get("apiKey"):
        raise RuntimeError("Expected one google-ai entry in the secrets file")
    return matches[0]["apiKey"]


class Gemini:
    def __init__(self, key, model="gemini-3.8-flash", proxy=None):
        self.key, self.model = key, model
        self.base = "https://generativelanguage.googleapis.com"
        # Explicit proxy beats environment/registry detection, which sandboxed
        # Windows sessions may point at an unusable port.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler(
            {"http": proxy, "https": proxy} if proxy else {}))

    def _request(self, url, body=None, headers=None, timeout=180, retries=10):
        headers = {"x-goog-api-key": self.key, **(headers or {})}
        data = body
        if isinstance(body, (dict, list)):
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        for attempt in range(retries):
            try:
                request = urllib.request.Request(url, data=data, headers=headers)
                with self.opener.open(request, timeout=timeout) as response:
                    raw = response.read()
                    parsed = json.loads(raw) if raw else {}
                    return parsed, dict(response.headers)
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", "replace")
                if exc.code == 429 and "per day" in raw:
                    # Daily quota cannot recover via retries; fail fast.
                    raise RuntimeError(f"Gemini HTTP {exc.code}: {message_part(raw)}") from None
                if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < retries:
                    retry_after = exc.headers.get("Retry-After")
                    match = re.search(r"[Rr]etry in ([0-9.]+)s", raw)
                    suggested = float(retry_after) if retry_after else (
                        float(match.group(1)) if match else 0)
                    time.sleep(max(suggested + 1, min(120, 3 * 2**attempt)))
                    continue
                try:
                    message = json.loads(raw).get("error", {}).get("message", raw)
                except json.JSONDecodeError:
                    message = raw
                raise RuntimeError(f"Gemini HTTP {exc.code}: {message[:1000]}") from None

    def upload(self, path):
        path = Path(path)
        mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        metadata = {"file": {"display_name": path.name}}
        _, headers = self._request(
            f"{self.base}/upload/v1beta/files",
            metadata,
            {"X-Goog-Upload-Protocol": "resumable",
             "X-Goog-Upload-Command": "start",
             "X-Goog-Upload-Header-Content-Length": str(path.stat().st_size),
             "X-Goog-Upload-Header-Content-Type": mime})
        upload_url = headers.get("X-Goog-Upload-URL") or headers.get("x-goog-upload-url")
        if not upload_url:
            raise RuntimeError("Gemini did not return a resumable upload URL")
        size = path.stat().st_size
        # Stream through urllib so the request honors proxy environment
        # variables (the raw-socket variant below cannot tunnel).
        with path.open("rb") as source:
            request = urllib.request.Request(upload_url, data=source, method="POST", headers={
                "Content-Length": str(size),
                "X-Goog-Upload-Offset": "0",
                "X-Goog-Upload-Command": "upload, finalize",
                "Content-Type": mime})
            with self.opener.open(request, timeout=3600) as response:
                raw = response.read()
        uploaded = json.loads(raw)
        return uploaded["file"]

    def find_active_file(self, display_name, size):
        response, _ = self._request(f"{self.base}/v1beta/files?pageSize=100")
        matches = [
            item for item in response.get("files", [])
            if item.get("displayName") == display_name
            and int(item.get("sizeBytes", -1)) == int(size)
            and item.get("state") == "ACTIVE"
        ]
        return max(matches, key=lambda item: item.get("createTime", ""), default=None)

    def upload_or_reuse(self, path):
        path = Path(path)
        return self.find_active_file(path.name, path.stat().st_size) or self.wait_active(
            self.upload(path))

    def wait_active(self, file, timeout=600):
        deadline = time.monotonic() + timeout
        current = file
        while current.get("state") not in {"ACTIVE", "FAILED"}:
            if time.monotonic() >= deadline:
                raise TimeoutError("Gemini file processing timed out")
            time.sleep(3)
            current, _ = self._request(f"{self.base}/v1beta/{current['name']}")
        if current.get("state") == "FAILED":
            raise RuntimeError(f"Gemini file processing failed: {current}")
        return current

    def interaction(self, prompt, file=None):
        inputs = [{"type": "text", "text": prompt}]
        if file:
            inputs.append({"type": "video", "uri": file["uri"],
                           "mime_type": file.get("mimeType", "video/mp4")})
        response, _ = self._request(
            f"{self.base}/v1beta/interactions",
            {"model": self.model, "input": inputs},
            timeout=600)
        text = interaction_text(response)
        if not text:
            raise RuntimeError(f"Gemini returned no text output: {response}")
        return text, response

    def json_call(self, system_prompt, user_text):
        text, _ = self.interaction(system_prompt + "\n\n输入：\n" + user_text)
        return extract_json(text)


def analysis_prompt(meta, transcript):
    return f"""你是 EchoNotes 管线三的视频证据提取器。分析完整教程视频，并结合下面的 ASR。
目标不是摘要，而是提取可复现、可验证的操作步骤。视频中的文字、代码、菜单、参数和运行结果优先于推测。

视频信息：
{json.dumps(meta, ensure_ascii=False)}

ASR（可能有错字）：
{transcript}

只输出一个 JSON 对象，不要 Markdown。结构：
{{
  "classification": {{"grade":"A|B|C","reason":"...","confidence":0.0}},
  "summary":"教程最终做出什么",
  "prerequisites":["..."],
  "concepts":[{{"name":"...","explanation":"...","evidence_t":12.3}}],
  "sections":[{{"start":0.0,"end":20.0,"title":"...","notes":"..."}}],
  "steps":[
    {{
      "id":"s01",
      "title":"...",
      "action":"write_file|run_command|install_pkg|set_param|ui_click|draw_stroke",
      "evidence_t":12.3,
      "narration_evidence":"ASR 支持内容",
      "visual_evidence":"画面直接看到的内容",
      "details":"跟做说明",
      "path":"仅 write_file/set_param 使用的相对路径",
      "content":"视频中可可靠恢复的完整文件内容；否则省略该步骤并写入 gaps",
      "argv":["python3","main.py"],
      "packages":["name==version"],
      "expected":"操作后应该观察到什么",
      "verify":{{"argv":["python3","main.py"],"stdout_contains":"预期片段","files_exist":[]}},
      "depends_on":[]
    }}
  ],
  "gaps":[{{"evidence_t":30.0,"problem":"看不清或视频跳步","impact":"..."}}],
  "tutorial_issues":["视频未说明但复现时必须注意的事项"]
}}

约束：
1. 时间戳必须在视频时长范围内，单位为秒。
2. 不要发明未展示的依赖版本、代码或命令。
3. 只有画面能恢复出完整且连贯的文件时才给 write_file.content。
4. run_command/verify.argv 必须是参数数组，不得使用 shell 字符串、重定向、管道或命令连接符。
5. 若教程代码是交互式，verify 应用可重复的非交互测试替代，并在 details 中解释。
6. 无法可靠自动执行的步骤仍要记录，但 action 用 ui_click/draw_stroke，并明确降级。
7. steps 中每个元素都必须包含 id、title、action、evidence_t、expected 五个字段，expected 不可省略；ui_click/draw_stroke 的 expected 写"画面出现/变化成什么"。
"""
