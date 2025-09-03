# AstrBot 快速参考指南

这是一个为 AstrBot 插件开发设计的模块化快速参考系统。每个文件专注于特定的开发主题，方便快速查找和上下文高效利用。

## 📂 参考模块目录

### 基础开发
- **[01_basic_structure.md](01_basic_structure.md)** - 插件基础结构、导入和元数据
- **[02_event_listeners.md](02_event_listeners.md)** - 事件监听器和过滤器类型
- **[03_message_handling.md](03_message_handling.md)** - 消息处理和组件构建

### 功能集成
- **[04_llm_integration.md](04_llm_integration.md)** - LLM调用和函数工具注册
- **[05_config_management.md](05_config_management.md)** - 配置管理和用户设置
- **[06_session_control.md](06_session_control.md)** - 会话控制和交互流程

### 高级功能
- **[07_async_tasks_network.md](07_async_tasks_network.md)** - 异步任务和网络请求
- **[08_data_persistence.md](08_data_persistence.md)** - 数据持久化和文件操作
- **[09_napcat_api.md](09_napcat_api.md)** - NapCat QQ平台API集成

### 实用工具
- **[10_image_utils.md](10_image_utils.md)** - 图像处理和实用工具
- **[11_common_patterns.md](11_common_patterns.md)** - 常见模式和最佳实践

## 🚀 快速开始

### 1. 基础插件模板
```python
from astrbot.api.event import AstrMessageEvent
from astrbot.core.plugin import BasePlugin, filter
from astrbot.api.platform import Context
from astrbot.core.config.config_models import ConfigModel, ConfigItem
from astrbot.api.plugin import PluginMetadata

class MyPlugin(BasePlugin):
    def __init__(self, context: Context):
        super().__init__(context)
        self.plugin_info = PluginMetadata(
            plugin_name="my_plugin",
            plugin_type="function",
            author="Your Name",
            desc="插件描述",
            version="1.0.0",
        )
    
    async def info(self) -> PluginMetadata:
        return self.plugin_info
    
    @filter.command("hello")
    async def hello(self, event: AstrMessageEvent):
        yield event.plain_result("Hello World!")
```

### 2. 常用导入
```python
# 核心模块
from astrbot.api.event import AstrMessageEvent
from astrbot.core.plugin import BasePlugin, filter
from astrbot.api.platform import Context

# 配置管理
from astrbot.core.config.config_models import ConfigModel, ConfigItem

# LLM集成
from astrbot.core.llm_manager import LLMManager
from astrbot.api.llm import RegisteredLLMTool, tool

# 日志
from astrbot.core.utils.logging import LogManager
logger = LogManager.GetLogger("my_plugin")
```

### 3. 开发工作流

1. **创建插件文件** - 使用 `01_basic_structure.md` 中的模板
2. **添加事件监听** - 参考 `02_event_listeners.md` 选择合适的过滤器
3. **处理消息** - 使用 `03_message_handling.md` 构建响应
4. **集成功能** - 根据需要参考相关模块文档

## 📋 开发检查清单

### 插件开发前
- [ ] 确认Python 3.10+环境
- [ ] 安装依赖: `uv sync`
- [ ] 创建所需目录: `mkdir -p data/plugins data/config data/temp`

### 插件开发中
- [ ] 实现基础结构 (模板、元数据、配置)
- [ ] 添加错误处理和日志记录
- [ ] 测试事件监听和消息处理
- [ ] 验证配置管理功能

### 插件开发后
- [ ] 运行代码检查: `uv run ruff check .`
- [ ] 格式化代码: `uv run ruff format .`
- [ ] 测试插件功能
- [ ] 更新插件文档

## 🔧 调试技巧

### 日志调试
```python
from astrbot.core.utils.logging import LogManager
logger = LogManager.GetLogger("my_plugin")

logger.debug("调试信息")
logger.info("一般信息")
logger.warning("警告信息")
logger.error("错误信息")
```

### 错误处理
```python
try:
    # 你的代码
    pass
except Exception as e:
    logger.error(f"错误: {e}")
    yield event.plain_result(f"处理失败: {str(e)}")
```

### 配置验证
```python
# 检查必要配置
if not self.config.api_key:
    yield event.plain_result("请先配置API密钥")
    return
```

## 🌟 最佳实践

1. **模块化设计** - 将复杂功能拆分为多个方法
2. **错误处理** - 始终包含适当的异常处理
3. **用户友好** - 提供清晰的错误信息和使用说明
4. **性能考虑** - 使用缓存和异步操作优化性能
5. **代码质量** - 遵循PEP 8规范，使用类型提示

## 📚 相关资源

- **AstrBot官方文档**: [GitHub仓库](https://github.com/Soulter/AstrBot)
- **插件示例**: `packages/` 目录下的官方插件
- **开发指南**: `.github/copilot-instructions.md`

## 💡 使用提示

- **快速查找**: 使用 Ctrl+F 在相关模块中搜索关键词
- **代码复用**: 复制模板代码后根据需要修改
- **组合使用**: 多个模块的示例可以组合使用
- **实时测试**: 使用 `uv run main.py` 启动AstrBot进行实时测试

---

*本参考指南设计为高效的开发辅助工具，专注于快速定位和最小化上下文窗口使用。*
