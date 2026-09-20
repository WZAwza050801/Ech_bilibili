# Ech_youtube

> EchoNotes 的 YouTube 版本（规划中）。

## 与 EchoNotes（Bilibili 版）的关系

复用 EchoNotes 的笔记层，只替换平台感知层：

| 层 | EchoNotes (Bilibili) | Ech_youtube (YouTube) |
|----|---------------------|----------------------|
| 视频/音频获取 | playurl API 直取 + 风控对抗 | yt-dlp（官方支持，无需对抗风控） |
| 视频列表 | wbi 签名 / playwright Edge 退避 | YouTube Data API 或 yt-dlp 频道遍历 |
| ASR 转写 | faster-whisper（复用） | 同左；有官方 CC 字幕时优先用字幕 |
| 格式整理 | polish.py（复用） | 同左 |
| 笔记渲染 | build_notes（复用） | 同左 |

## 从 Bilibili 版继承的经验

- 三道完整性校验（转写时长 / 字数漂移 / 缓存复检）——YouTube 也可能有截断下载
- 串行批量铁律、OOM 冷却重试、产物回收站机制
- 详见主仓库 README 的"稳定性设计"

## 状态

📋 规划中。Bilibili 版跑稳后启动。
