# 断点快照 · 2026-09-20 14:45

> 恢复时对我说"继续跑批量"即可，我会执行 `python work/pipeline1/batch_run.py`（后台）接着干。

## 0. 最新断点

- **Ech_youtube 已实现并跑通** ✅（2026-09-20）：`Ech_youtube/` 自包含目录，yt-dlp 取流 → ASR/polish/笔记复用 B 站版设计；"Me at the zoo" 端到端冒烟 21s 通过。yt-dlp 2026.8.19 已装进 venv（wheel 文件名补全后 --no-deps 本地安装，因 env 代理 2213 是坏的、pip 在线装不了）
- **GitHub 仓库已更名**：EchoNotes → **WZAwza050801/Ech_bilibili**（旧地址自动跳转），本地 remote 已同步，Ech_youtube 代码已推送（179a2b2）
- **OOM 已修复**：ctranslate2 "bad allocation" —— `transcribe_local.py` 已加 `cpu_threads=4`（限制线程降内存峰值），实测连续多个视频稳定通过，勿改回
- **假产物已清零**：23 篇假笔记全删并重做
- **进度**：✅ 管线一收官（2026-09-21）——114 期清单：完成 111，充电专属 3 期无法获取（页面实测充电+试看标记，仅 180s 试看流），真实性复检全过，index 终版 + 归档报告.md 已生成并推送 GitHub（586df6e）
- **教训**：不要并发跑两个 batch（work 根中转文件互相踩，踩过一次）

## 一、当前进度

| 事项 | 状态 |
|------|------|
| GitHub 仓库 | ✅ https://github.com/WZAwza050801/Ech_bilibili（已更名） |
| Ech_youtube | ✅ 已实现并跑通（yt_pipeline.py / yt_batch.py / 双语言 polish），代理默认走 127.0.0.1:12000（YT_PROXY 可覆盖） |
| 视频列表 | ✅ 114/124（差最老 10 个，可后续冷却重试 fetch_list_retry2.cjs 或搜索兜底） |
| 读书笔记批量 | ✅ 收官：111/114 完成，3 期充电专属（BV1bH4aeAE7E / BV1o4421Q7KG / BV1FJ4m1W71F），详见 江左道卡卡-读书笔记/归档报告.md |

## 二、踩坑记录（重要）

1. **假产物链**：风控掐断音频下载 → 截断 m4s 被 ffmpeg"假成功"转换 → 假 wav 转写半截笔记。防线：三道校验（转写时长≥95% / polish 字数漂移±30% / 缓存命中复检）+ 截断产物移 `runs/_trash/`
2. **残留转写误 copy**：转写 subprocess 崩溃时上一视频的 transcript 被误当当前产物（261s 之谜=某 4:21 视频）。已修：转写前清 work 根残留 + 严格校验
3. **OOM 两连**：昨晚 `mkl_malloc`（系统 commit 内存耗尽，重启解决）；今天 `bad allocation`（ctranslate2 线程 workspace 峰值，`cpu_threads=4` 解决）
4. **batch 并发互踩**：两个 batch 同时跑会抢 work 根的 audio.wav/transcript.json → 永远串行
5. **sandbox 批量删除拦截**：unlink 超阈值被拦，改用 rm() 移入 `runs/_trash/`

## 三、剩余收尾（批量跑完后）

1. 全量真实性复检（脚本：比对笔记内 BV 号 ↔ runs 转写时长）
2. 补最后 10 个视频列表 → 补跑
3. 按 日期+标题 归档重整笔记文件夹 + index.html 卡片墙更新
4. 提交 GitHub
5. 用户新开文件夹做管线二（课程→LaTeX 讲义）和管线三（实操→复刻+实验报告），提示词已给

## 四、相关文件

- 总控：`work/pipeline1/pipeline1.py`（三道校验+rm回收）
- 批量：`work/pipeline1/batch_run.py`（断点续跑+OOM重试）
- 转写：`work/pipeline1/transcribe_local.py`（int8 + cpu_threads=4）
- 列表：`work/pipeline1/video_list.json`（114个）
- 日志：`江左道卡卡-读书笔记\batch_log.txt`
- YouTube 版：`Ech_youtube/`（yt_pipeline.py 总控 / yt_batch.py 批量 / polish.py 双语言 / transcribe_local.py 自动语种检测，模型与 B 站版共享目录）
