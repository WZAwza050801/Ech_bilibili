> 本仓库（管线一）只需要：**DeepSeek API Key**（polish 格式整理）+ 本地 faster-whisper/ffmpeg。

# API 配置指南

> 拿到本仓库后，按本指南申请并配置 API Key，即可跑通管线。**任何密钥都不要提交进仓库**
> （.gitignore 已拦截常见密钥文件，但请自觉）。

## 一、总览：哪个阶段用哪个 API

| 阶段 | 管线一<br>读书笔记 | 管线二<br>LaTeX 讲义 | 管线三<br>复刻作品集 | 模型 | 必需性 |
|---|---|---|---|---|---|
| 语音转写 ASR | ✅ 本地 | ✅ 本地 | ✅ 本地 | faster-whisper small/int8 | 无需 API（本地跑） |
| 视觉理解（看视频帧） | — | ✅ | ✅ | Qwen3-VL-32B-Instruct | **必需** |
| 规划（知识块编排） | — | ✅ | — | qwen3.8-max | 必需 |
| 写作/审校 | ✅ polish | ✅ | — | kimi-k3 / deepseek-chat | 必需 |
| 讲义渲染 | — | ✅ | — | XeLaTeX（本地） | 无需 API |
| 作品渲染 | — | — | ✅ | Godot + ffmpeg（本地） | 无需 API |

**最少配置**：管线一只需 1 个 Key（DeepSeek）；管线二需 3 个（硅基流动 + 百炼 + Kimi）；
管线三需 1 个（硅基流动）。

## 二、密钥放哪：两种方式任选

**方式 A · 环境变量**（最简单）

```powershell
$env:SILICONFLOW_API_KEY = "sk-xxx"   # 管线二/三 视觉
$env:DEEPSEEK_API_KEY    = "sk-xxx"   # 管线一 polish
$env:GEMINI_API_KEY      = "xxx"      # 仅当坚持用 Gemini（见第四节）
```

**方式 B · 密钥文件**（统一管理多个 Key）

```json
{
  "entries": [
    { "provider": "siliconflow", "apiKey": "sk-xxx" },
    { "provider": "google-ai",   "apiKey": "xxx" }
  ]
}
```

启动时传 `--secrets 路径.json`，或设 `ECHONOTES_SECRETS_FILE` 环境变量。
管线二的规划/写作 Key 按 `KEY_LABEL` 标签从同一文件读取（见下文）。

## 三、各服务详解

### 1. 硅基流动 SiliconFlow —— 视觉理解（管线二/三必需）

- **干什么**：看视频抽帧画面，产出结构化分析（管线三）或知识块 map（管线二）。
- **为什么选它**：需要**多模态视觉模型**且能**国内直连**。首选 Gemini 因中国大陆
  区域不可用（实测返回地区限制错误），**平替就是 Qwen3-VL**——开源多模态、
  视频帧理解质量接近、价格低（本管线约合每分P几毛钱）、无需科学上网。
- **在哪申请**：https://siliconflow.cn → 注册后在「API 密钥」页新建（新用户送额度）。
- **配置**：`SILICONFLOW_API_KEY` 或 secrets 文件 `provider: "siliconflow"`。
- **实测模型**：`Qwen/Qwen3-VL-32B-Instruct`（帧列表模式，900s 超时 × 8 重试）。

### 2. 阿里云百炼（token plan）—— 规划（管线二）

- **干什么**：把每个 10 分钟窗口的转写+截图编排成知识块（定义/步骤/参数）。
- **为什么选它**：实测 **JSON 模式输出稳定、数学内容正常**，且走 **token plan 订阅制**
  不按量扣费。同系 dashscope 按量接口也可用，但请注意计费方式。
- **在哪申请**：https://bailian.console.aliyun.com → 开通模型服务 →
  订阅 token plan（或使用按量计费）。
- **配置**：`ECHONOTES_PLANNER_PROVIDER=bailian`、
  `ECHONOTES_PLANNER_BASE_URL=https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1`、
  `ECHONOTES_PLANNER_MODEL=qwen3.8-max`，Key 按 `ECHONOTES_PLANNER_KEY_LABEL`
  标签从密钥文件读取。

### 3. Kimi（Moonshot）—— 写作/审校（管线二）

- **干什么**：把知识块写成讲义正文——长文组织与中文表达质量是第一要求。
- **为什么选它**：实测长文写作质量最好；走 **Kimi Code Plan 订阅**不按量扣费。
  注意该端点**强制 temperature=1**（不可调低）。
- **在哪申请**：https://www.kimi.com 订阅 Code Plan；或开放平台
  https://platform.moonshot.cn 按量使用 `moonshot-v1` 系列。
- **配置**：`ECHONOTES_WRITER_PROVIDER=kimi-code`、
  `ECHONOTES_WRITER_BASE_URL=https://api.kimi.com/coding/v1`、
  `ECHONOTES_WRITER_MODEL=kimi-k3`、`ECHONOTES_WRITER_TEMPERATURE=1`、
  `ECHONOTES_WRITER_MAX_TOKENS=8192`，Key 按 `ECHONOTES_WRITER_KEY_LABEL` 读取。

### 4. DeepSeek —— 格式整理（管线一）

- **干什么**：只做加标点/繁转简/同音错字修正（prompt 硬约束禁改写）。
- **为什么选它**：这类格式活不需要贵模型，DeepSeek 便宜且中文标点规则稳定。
- **在哪申请**：https://platform.deepseek.com → 充值后建 Key（按量，polish 一条视频约几分钱）。
- **配置**：`DEEPSEEK_API_KEY` 环境变量。

### 5. 本地 ASR faster-whisper —— 全管线通用（无 API）

- **干什么**：语音转带时间戳文字稿。
- **配置**：无需 Key。模型从 HuggingFace 下载 `Systran/faster-whisper-small`
  放到本地目录，用 `ECHONOTES_ASR_MODEL` 指向；`ECHONOTES_ASR_PYTHON` 指向装了
  faster-whisper 的 Python。另需 `ffmpeg` 在 PATH。

### 6. Gemini —— 为什么默认不用

- **原因**：官方 API 对中国大陆区域不可用（实测请求返回地区限制错误），且需要代理。
- **平替**：视觉任务用硅基流动 Qwen3-VL（能力相当、国内直连）；
  代码中 `gemini.py` 保留，`GEMINI_API_KEY` 可用时可切回（管线三 `--provider gemini`）。

## 四、配置完自检（各一条最小命令）

```bash
# 硅基流动
curl https://api.siliconflow.cn/v1/models -H "Authorization: Bearer $SILICONFLOW_API_KEY"
# DeepSeek
curl https://api.deepseek.com/models -H "Authorization: Bearer $DEEPSEEK_API_KEY"
# Kimi Code Plan
curl https://api.kimi.com/coding/v1/models -H "Authorization: Bearer <kimi-key>"
# 百炼 token plan
curl https://token-plan.cn-beijing.maas.aliyuncs.com/compatible-mode/v1/models -H "Authorization: Bearer <bailian-key>"
```

返回模型列表 JSON 即为通。另外确认 `ffmpeg -version`、`xelatex --version`（管线二）可用。

## 五、安全须知

- 密钥文件放在**仓库目录之外**（本项目惯例是本地"密码书"目录）；
- `.gitignore` 已拦截常见密钥文件名，但新增文件请自查 `git status`；
- 提交前可跑 `git grep -i "sk-"` 快速扫一遍暂存内容；
- Key 泄漏的第一时间去对应平台吊销重发。
