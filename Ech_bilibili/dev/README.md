# dev/ — 探路脚本留档（非产品代码）

这里放的是 B 站适配过程中写的一次性脚本，**不参与管线运行，不要在生产路径里调用**。
保留它们是为了留下「风控对抗怎么打下来的」过程证据——这是本项目最难啃的一段。

| 文件 | 当时在解决什么 |
|---|---|
| `debug_playurl.py` / `debug_full_resp.py` / `debug_variants*.py` | 对比不同请求头 / cookie 组合下 playurl 的返回，定位 412 的触发条件 |
| `debug_fresh_buvid.py` / `make_cookiejar.py` / `bili_app_cookies.py` | 获取与组装匿名 buvid3/buvid4/b_nut 等 cookie 组 |
| `debug_tv_api.py` / `gen_tv_url.py` | TV 端接口取流方案试探（最终未采用） |
| `extract_media_url.py` / `dl_browser_stream.py` | 从浏览器会话里直接抓媒体流（绕开 API 的备份路线） |
| `check_login.py` / `check_ff_cookies.py` / `copy_locked.py` | 登录态与浏览器 cookie 库（含被占用时的复制）排查 |
| `test_playurl_auth.py` | 带鉴权与不带鉴权的 playurl 对照实验 |
| `fetch_list_browser.cjs` / `fetch_list_retry.cjs` | 列表抓取的早期浏览器方案（**现役版本是 `../fetch_list_retry2.cjs`**） |
| `make_notes.py` / `build_html.py` / `finalize.py` | 笔记渲染 / 收尾的早期实现，逻辑已并入 `../pipeline1.py` 的 `render_notes()` |
| `debug_patient_out.json` / `fresh_buvid.json` / `video_list_partial.json` | 上述脚本的中间输出样本 |

**现役产品代码都在上一层 `Ech_bilibili/`**：`pipeline1.py`、`batch_run.py`、`transcribe_local.py`、
`polish.py`、`hotfix.json`、`fetch_list.py`、`fetch_list_retry2.cjs`、`cleanup_fake.py`、`retry3.py`、`probe_ports.py`。

> 想清理的话可以直接删掉整个 `dev/`，不影响管线；历史都在 git 里。
