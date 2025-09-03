# 🎭 AstrBot TTS 情绪路由插件

[![Version](https://img.shields.io/badge/version-0.2.1-blue.svg)](https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/)

> 智能情绪识别的 TTS 插件，根据对话情绪自动切换音色与语速，让你的 AstrBot 更有感情！

## ✨ 核心特性

### 🧠 智能情绪识别
- **隐藏标记解析**：支持 `[EMO:happy]`、`【EMO：开心】`、`&happy&` 等多种情绪标签格式
- **启发式分类**：无标记时自动分析文本情绪（开心、难过、愤怒、中性）
- **上下文感知**：结合对话历史进行情绪判断

### 🎵 音色语速路由
- **情绪音色映射**：不同情绪自动使用不同的语音音色
- **动态语速调节**：开心加速 1.2x，难过减速 0.85x，完美还原情感
- **硅基流动 API**：支持 CosyVoice 等高质量 TTS 模型

### 🛡️ 智能文本处理
- **代码块过滤**：自动识别并跳过 ```代码``` 和 `行内代码`
- **表情符号处理**：智能过滤 emoji 和 QQ 表情，避免朗读 `[微笑]` `😀`
- **链接检测**：自动跳过 URL 和文件路径
- **文本优化**：防止 TTS 吞字，确保完整朗读

### ⚡ 高级控制
- **会话级开关**：每个对话独立控制 TTS 开关
- **概率门控**：可设置触发概率，避免过度朗读
- **长度限制**：超长文本自动跳过，专注短句对话
- **冷却机制**：防止频繁触发，优化体验

## 🚀 快速开始

### 📋 环境要求

- **AstrBot** v3.5+ 
- **Python** 3.8+
- **ffmpeg**（音频处理必需）
- **硅基流动 API Key**（或其他兼容的 OpenAI 语音 API）

### 📦 安装步骤

1. **下载插件**
   ```bash
   cd data/plugins/
   git clone https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router.git tts_emotion_router
   ```

2. **安装 ffmpeg**
   ```bash
   # Ubuntu/Debian
   sudo apt install ffmpeg
   
   # Windows (使用 chocolatey)
   choco install ffmpeg
   
   # macOS
   brew install ffmpeg
   ```

3. **安装依赖**
   ```bash
   cd /path/to/astrbot
   uv sync  # requests 已包含在 AstrBot 依赖中
   ```

4. **启动 AstrBot**
   ```bash
   uv run main.py
   ```

5. **打开配置面板**
   - 访问：http://localhost:6185
   - 进入插件管理 → TTS情绪路由插件

### 推荐可与STT插件配合实现与bot全语音交流
##https://github.com/NickCharlie/Astrbot-Voice-To-Text-Plugin
### ⚙️ 基础配置

<details>
<summary><b>🔧 API 配置（必填）</b></summary>

| 配置项 | 示例值 | 说明 |
|--------|--------|------|
| `api.url` | `https://api.siliconflow.cn/v1` | API 服务地址 |
| `api.key` | `sk-xxx` | 你的 API Key |
| `api.model` | `FunAudioLLM/CosyVoice2-0.5B` | TTS 模型名称 |
| `api.format` | `mp3` | 音频格式（推荐 mp3） |
| `api.speed` | `1.0` | 默认语速 |

</details>

<details>
<summary><b>🎭 情绪路由配置</b></summary>

```yaml
# 音色映射（必须至少配置 neutral）
voice_map:
  neutral: "FunAudioLLM/CosyVoice2-0.5B:anna"    # 中性音色
  happy: "FunAudioLLM/CosyVoice2-0.5B:cheerful"  # 开心音色
  sad: "FunAudioLLM/CosyVoice2-0.5B:gentle"      # 难过音色
  angry: "FunAudioLLM/CosyVoice2-0.5B:serious"   # 愤怒音色
  # 自定义音色从"speech"开始填写
  # neutral: "speech:sad-zhizhi-voice:icwcmuszkb:vdpjnvpfqbqbsywmbyly"

# 语速映射（自己按喜欢设置）
speed_map:
  neutral: 1.0    # 正常语速
  happy: 1.2      # 开心加速
  sad: 0.85       # 难过减速
  angry: 1.1      # 愤怒略快
```

</details>

<details>
<summary><b>🏷️ 情绪标签配置</b></summary>

```yaml
emotion:
  marker:
    enable: true        # 启用隐藏标记解析
    tag: "EMO"          # 标签名称，对应 [EMO:happy]
    prompt_hint: |      # 复制到系统提示中
      请在每次回复末尾追加形如 [EMO:<happy|sad|angry|neutral>] 的隐藏标记。
      该标记仅供系统解析，不会展示给用户。
```

</details>

## 🎯 使用指南

### 💡 推荐配置流程
<img width="580" height="1368" alt="PixPin_2025-08-25_17-00-01" src="https://github.com/user-attachments/assets/6cd57fb9-9b39-4dae-80e4-c9bd0c3400de" />

1. **配置系统提示**
   在你的 AI 人格设定中添加：
   ```
   请在每次回复末尾追加形如 [EMO:<happy|sad|angry|neutral>] 的隐藏标记。
   该标记仅供系统解析，不会展示给用户。开心时用 happy，难过时用 sad，
   愤怒时用 angry，其他情况用 neutral。
   ```

2. **测试情绪识别**
   ```
   用户：今天天气真不错！[EMO:happy]
   机器人：是的，阳光明媚的日子总是让人心情愉悦呢！[EMO:happy]
   ```

3. **调试和优化**
   ```bash
   tts_test_problematic  # 测试问题文本处理
   tts_debug 测试文本   # 查看处理过程
   tts_status           # 查看当前状态
   ```

### 🎮 会话控制命令

| 命令 | 功能 | 示例 |
|------|------|------|
| `tts_on` | 当前会话启用 | 开启语音回复 |
| `tts_off` | 当前会话禁用 | 关闭语音回复 |
| `tts_global_on` | 全局启用 | 所有会话默认开启 |
| `tts_global_off` | 全局禁用 | 所有会话默认关闭 |
| `tts_prob 0.8` | 设置触发概率 | 80% 概率触发 |
| `tts_limit 100` | 设置长度限制 | 超过100字跳过 |
| `tts_cooldown 30` | 设置冷却时间 | 30秒内不重复 |
| `tts_status` | 查看状态 | 显示当前配置 |

### 🏷️ 支持的情绪标签格式

插件支持多种情绪标签格式，会自动识别并移除：

```
标准格式：[EMO:happy] [EMO:sad] [EMO:angry] [EMO:neutral]
中文格式：【EMO：开心】【EMO：难过】【EMO：愤怒】【EMO：中性】
简短格式：happy: sad: angry: neutral:
符号格式：&happy& &sad& &angry& &neutral&
情绪格式：【情绪：开心】【情绪：难过】
```

### 🛡️ 智能文本过滤示例

```python
# 原始文本
"看看这个代码 `print('hello')` 很简单吧！😊 [微笑]"

# 处理后文本（用于TTS）
"看看这个代码很简单吧！"

# 被过滤的内容
- 行内代码：`print('hello')`
- Emoji：😊
- QQ表情：[微笑]
```

## 🔧 故障排除

### ❌ 常见问题

<details>
<summary><b>Q: 没有语音输出，只有文字</b></summary>

**可能原因：**
1. API 配置错误
2. 网络连接问题
3. ffmpeg 未安装
4. 音色配置不存在

**解决步骤：**
```bash
# 1. 检查 API 配置
tts_debug 测试文本

# 2. 检查网络
curl -I https://api.siliconflow.cn/v1/audio/speech

# 3. 检查 ffmpeg
ffmpeg -version

# 4. 检查日志
# 查看 AstrBot 控制台输出的错误信息
```

</details>

<details>
<summary><b>Q: 情绪不切换，总是同一个音色</b></summary>

**解决方案：**
1. **启用标记解析**：确保 `emotion.marker.enable = true`
2. **配置音色映射**：检查 `voice_map` 中各情绪音色是否配置
3. **系统提示**：在 AI 设定中添加情绪标记提示
4. **测试启发式**：发送明显情绪的文本（如"太棒了！"）

</details>

<details>
<summary><b>Q: TTS 朗读了代码块和表情符号</b></summary>

这已经在最新版本中修复！插件会自动过滤：
- Markdown 代码块：```代码```
- 行内代码：`代码`
- Emoji 表情：😊 🎉 等
- QQ 表情：[微笑] [大笑] 等
- 情绪标签：所有格式的情绪标记

</details>

<details>
<summary><b>Q: 概率、长度、冷却不生效</b></summary>

**检查配置：**
```bash
tts_status  # 查看当前设置

# 重新设置
tts_prob 1.0      # 100% 触发
tts_limit 999     # 取消长度限制  
tts_cooldown 0    # 取消冷却
```

</details>

### 🔍 调试工具

```bash
# 文本处理调试
tts_debug "你好！😊 [EMO:happy]"

# 问题文本测试
tts_test_problematic

# 查看会话状态
tts_status

# 检查插件日志
# 在 AstrBot 控制台查看详细输出
```

## 🎨 高级用法

### 🎭 自定义音色上传

使用音色上传工具：[下载地址](https://github.com/muyouzhi6/astrabot_plugin_tts_emotion_router/releases/tag/v0.1.1)

**需要准备：**
- 5MB 以下的 10 秒左右清晰人声素材
- 对应的文本内容
- 硅基流动 API Key（建议独立申请）

### 🔄 与其他插件配合

**STT 语音识别插件：**
```
配合 https://github.com/NickCharlie/Astrbot-Voice-To-Text-Plugin
实现完整的语音对话体验：语音输入 → 文字回复 → 情绪 TTS
```

### ⚡ 性能优化

```yaml
# 高频对话场景
prob: 0.6           # 降低触发概率
text_limit: 50      # 限制长文本
cooldown: 15        # 增加冷却时间

# 低延迟场景  
api.format: "mp3"   # 使用 MP3 格式
max_retries: 1      # 减少重试次数
timeout: 15         # 缩短超时时间
```

## 🔬 技术原理

### 🧠 情绪分类算法

1. **隐藏标记优先**：检测并解析 `[EMO:xxx]` 等格式标记
2. **启发式分析**：基于关键词、标点符号、上下文推断
3. **规则引擎**：
   - 积极词汇 → happy（开心、太棒了、哈哈）
   - 消极词汇 → sad（难过、失望、唉）  
   - 愤怒词汇 → angry（生气、愤怒、气死）
   - 信息性内容 → neutral（链接、代码等）

### 🎵 音色路由机制

```python
情绪识别 → 查找音色映射 → 应用语速调节 → TTS 合成 → 音频输出
    ↓           ↓           ↓          ↓        ↓
  happy    → cheerful  →   1.2x   →   API   → xxx.mp3
```

### 🛡️ 文本处理流程

```
原始文本 → 过滤代码块 → 过滤表情 → 清理标签 → 添加结尾 → TTS合成
```

## 📈 版本历史

- **v0.2.1** (当前)
  - 🆕 新增代码块和表情符号过滤
  - 🆕 支持 `&emotion&` 标签格式
  - 🔧 修复 TTS 吞字问题
  - 🔧 修复事件传播中断问题
  - ⚡ 优化文本处理性能

- **v0.1.0**
  - 🎉 首个发布版本
  - ✅ 基础情绪识别和音色路由
  - ✅ 硅基流动 API 集成

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支：`git checkout -b feature/amazing-feature`
3. 提交改动：`git commit -m '添加某个特性'`
4. 推送分支：`git push origin feature/amazing-feature`
5. 提交 Pull Request

## 📄 开源协议

本项目基于 MIT 协议开源 - 查看 [LICENSE](LICENSE) 文件了解详情。

## 👨‍💻 作者信息

- **作者**：木有知
- **仓库**：https://github.com/muyouzhi6/astrbot_plugin_tts_emotion_router
- **版本**：0.2.1

---

<div align="center">
  
**🌟 如果这个插件对你有帮助，请给个 Star 支持一下！**

*让每一句话都充满感情！*

</div>
