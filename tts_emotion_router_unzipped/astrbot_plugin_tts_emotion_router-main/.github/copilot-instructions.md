# Copilot instructions for astrbot_plugin_tts_emotion_router

本仓库是一个 AstrBot 插件：按情绪将 LLM 文本路由到不同音色/语速的 TTS，并在装饰阶段把文本替换为语音消息（Record）。本说明面向 AI 编码代理，帮助快速、安全地改动代码。

## 架构与数据流（大图）
- 入口星：`main.py` 的 `TTSEmotionRouter`。
  - Hook 顺序：
    - `on_llm_request` 向系统提示注入“隐藏情绪标记”指令（要求回复以 `[EMO:happy|sad|angry|neutral]` 开头）。
    - `on_llm_response` 从 `completion_text` 与结果链首个 `Plain` 中剥离该标记，并将解析到的情绪暂存到会话态。
    - `on_decorating_result` 最终装饰：清洗文本→门控（长度/冷却/概率/混合内容）→情绪与音色选择→TTS 合成→用 `Record(file=...)` 覆盖结果链。
- 情绪：
  - 枚举在 `emotion/infer.py`（常量 `EMOTIONS`）。
  - 分类优先级：会话态的隐藏标记 → 启发式分类器 `emotion/classifier.py`（轻量规则，含“中性偏置”）。
- TTS：`tts/provider_siliconflow.py` 的 `SiliconFlowTTS.synth(text, voice, out_dir, speed=None) -> Path|None` 写文件到 `temp/<session>/`。
- 去重：
  - 事件级：`_event_guard`（8s）+ `_processing_events` 防重入。
  - TTS 请求级：`SessionState.last_tts_sig/last_tts_time`（5s，同文本+音色+语速则跳过生成）。

## 配置与约定
- 支持两种配置来源：
  - 面板配置：`AstrBotConfig`（优先，首次部署会从插件本地 `config.json` 迁移已知字段）。
  - 旧版本地：插件目录 `config.json`（加载时与传入配置合并）。
- 关键键位（`self.config`）：
  - 基础：`global_enable`、`enabled_sessions`、`disabled_sessions`、`prob`、`text_limit`、`cooldown`、`allow_mixed`。
  - API：`api.url`、`api.key`、`api.model`(默认 `gpt-tts-pro`)、`api.format`(默认 `wav`)、`api.speed`(默认 `0.9`)、`api.gain`、`api.sample_rate`。
  - 路由：`voice_map`（情绪→音色URI）、`speed_map`（情绪语速倍率）。
- 环境密钥：优先读取系统变量 `SILICONFLOW_API_KEY`（不要将 Key 写入仓库）。
- 文本清洗：`_normalize_text`、`_strip_emo_head_many`、`_strip_leading_mentions`；过滤链接/文件扩展名、纯符号/纯数字、过短文本等。

## 开发与调试工作流
- 依赖：`pip install -r requirements.txt`。
- 运行：按你的 AstrBot 启动方式（示例：`python -m astrbot` 或项目入口）。
- 快速验证（在聊天内）：
  - `tts_clear` 清理状态 → 发送短句触发 → `tts_debug` 查看当前参数与队列规模。
  - 调优：`tts_format wav|mp3|aac|opus`、`tts_gain <dB>`、`tts_prob <0..1>`、`tts_limit <n>`、`tts_cooldown <s>`。
- 日志关注：`TTS route:`、`skip duplicate event`、`skip duplicate TTS` 等。

## 项目惯例与注意事项
- 仅在 `on_decorating_result` 的最后一步将 `result.chain` 完整替换为单个 `Record`，避免上游重试/多次装饰导致重复发送。
- 始终在生成音频前通过所有门控：冷却→长度→概率→情绪/音色→去重→合成→设置 `Record`。
- 临时文件：使用 `utils/audio.ensure_dir` 创建 `temp/` 子目录；`cleanup_dir` 已在初始化定时清理，勿直接删除运行中的文件夹。
- Provider 合约：`synth` 失败返回 `None`；调用方必须在失败时保持文本回退或直接返回，不要留置半成品 `Record`。

## 典型改动入口（示例）
- 新增聊天命令：参考 `@filter.command("tts_gain")` 等，返回 `event.plain_result(...)` 文本。
- 调整情绪→音色：在配置的 `voice_map` 中新增键值（至少保证 `neutral` 有效）。
- 拓展过滤：在 `_do_tts_processing` 文本清洗后追加正则/规则；保持返回前不改变 `result.chain`。
- Provider 调优：在 `tts/provider_siliconflow.py` 增加重试、超时、质量参数或文件体积校验。

## 关键文件索引
- `main.py`：星实现 + Hooks + 命令 + 去重。
- `emotion/infer.py`：`EMOTIONS` 常量。
- `emotion/classifier.py`：启发式分类器。
- `tts/provider_siliconflow.py`：硅基流动 TTS 客户端。
- `utils/audio.py`：目录保障与临时清理。
- `_conf_schema.json`、`metadata.yaml`、`requirements.txt`：配置架构、元数据与依赖。
