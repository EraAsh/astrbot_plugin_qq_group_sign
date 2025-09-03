# 插件基础结构模板

## 最小插件模板
```python
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("plugin_name", "author", "插件描述", "1.0.0", "repo_url")
class MyPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)

    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        '''这是一个示例指令'''
        yield event.plain_result("Hello, World!")

    async def terminate(self):
        '''插件被卸载时调用'''
        pass
```

## 带配置的插件模板
```python
from astrbot.api import AstrBotConfig

@register("plugin_name", "author", "插件描述", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 读取配置
        self.api_key = config.get("api_key", "")
        self.max_retries = config.get("max_retries", 3)
```

## 目录结构
```
my_plugin/
├── main.py              # 主插件文件 (必须)
├── metadata.yaml        # 插件元数据 (必须)
├── requirements.txt     # 依赖文件 (可选)
├── _conf_schema.json    # 配置Schema (可选)
└── README.md           # 说明文档 (推荐)
```

## metadata.yaml 模板
```yaml
name: "my_plugin"
author: "your_name"
description: "插件描述"
version: "1.0.0"
repo: "https://github.com/your_name/your_plugin"
tags: ["工具", "娱乐"]
license: "MIT"
python_version: ">=3.8"
astrbot_version: ">=3.4.0"
```

## 核心导入
```python
# 基础导入
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

# 消息组件
import astrbot.api.message_components as Comp

# 配置
from astrbot.api import AstrBotConfig

# LLM相关
from astrbot.api.provider import ProviderRequest, LLMResponse

# 会话控制
from astrbot.core.utils.session_waiter import session_waiter, SessionController
```

## 强制规则检查清单
- [ ] 使用 `from astrbot.api import logger` 而不是 logging
- [ ] 数据存储在 `data/` 目录，不是插件目录
- [ ] 使用 aiohttp/httpx，不使用 requests
- [ ] 运行 `uv run ruff check .` 检查代码
- [ ] 运行 `uv run ruff format .` 格式化代码
- [ ] 函数有适当的错误处理
- [ ] Handler 函数必须在插件类中定义
