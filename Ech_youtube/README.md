# Ech_youtube

> Ech_bilibili 的 YouTube 版本。**状态：✅ 已实现并跑通**（单视频端到端 21s 冒烟测试通过，2026-09-18）。

## 与 Ech_bilibili 的关系

笔记层完全复用 Ech_bilibili 的设计，只替换平台感知层：

| 层 | Ech_bilibili | Ech_youtube |
|----|-------------|-------------|
| 元数据 | view API + 完整浏览器头/cookie（风控对抗） | yt-dlp `extract_info`（官方支持，无需对抗风控） |
| 音频获取 | playurl API 直取 m4s + 截断校验 | yt-dlp `bestaudio/best` → ffmpeg 转 16k 单声道 wav |
| 语言 | 固定中文 | `auto` 自动检测（支持 zh/en/ja 等，可显式指定） |
| ASR 转写 | faster-whisper small/int8（共享同一模型目录，不重复下载） | 同左 |
| 格式整理 | polish.py 中文模式（标点/繁转简/热修词典） | polish.py 双模式：中文同左；其他语言仅标点+大小写，禁改写 |
| 笔记渲染 | 同款 HTML（蓝色 YouTube 主题） | 同款 HTML |
| 批量 | batch_run.py + 卡片墙 | yt_batch.py + 卡片墙（videos.txt 每行一个 URL/id） |

## 从 Bilibili 版继承的稳定性设计

- **三道完整性校验**：转写时长 ≥ 视频时长 95% / polish 字数漂移 ±30% / 缓存命中也复检
- **串行批量铁律**（并发会撞 work 根目录）、OOM 冷却重试（180s×2）
- **trash 回收站**代替直接删除、work 根残留清理（防上一视频产物误回收）
- 代理：默认 `http://127.0.0.1:12000`，可用环境变量 `YT_PROXY` 覆盖（`direct` = 直连）

## 用法

```bash
# 单视频（URL 或裸 id 均可）
python yt_pipeline.py https://www.youtube.com/watch?v=jNQXAC9IVRw
python yt_pipeline.py jNQXAC9IVRw en        # 显式指定语言

# 批量：把 URL/id 每行一个写进 videos.txt，然后
python yt_batch.py [输出文件夹名]
```

产出：`runs/<video_id>/笔记.html`（信息卡 + 整理版逐字稿分节 + 原始转写折叠可查证）。

## 已知限制

- 年龄限制/会员视频需要 cookies（yt-dlp `cookiesfrombrowser` 配置，暂未接）
- 有官方 CC 字幕的视频目前仍走 ASR（后续可加"字幕优先"分支）
- 直播/超长视频未测试
