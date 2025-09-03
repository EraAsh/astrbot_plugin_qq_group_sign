# 配置管理快速参考

## 配置Schema文件 (_conf_schema.json)
```json
{
  "api_key": {
    "description": "API密钥",
    "type": "string",
    "hint": "请输入您的API密钥",
    "obvious_hint": true
  },
  "max_retries": {
    "description": "最大重试次数",
    "type": "int",
    "default": 3
  },
  "enable_debug": {
    "description": "启用调试模式",
    "type": "bool",
    "default": false
  },
  "server_config": {
    "description": "服务器配置",
    "type": "object",
    "items": {
      "host": {
        "description": "服务器地址",
        "type": "string",
        "default": "localhost"
      },
      "port": {
        "description": "端口号",
        "type": "int",
        "default": 8080
      }
    }
  },
  "mode": {
    "description": "运行模式",
    "type": "string",
    "options": ["mode1", "mode2", "mode3"],
    "default": "mode1"
  },
  "code_config": {
    "description": "代码配置",
    "type": "text",
    "editor_mode": true,
    "editor_language": "json",
    "editor_theme": "vs-dark"
  }
}
```

## 配置字段类型
- `string`: 字符串输入框
- `text`: 大文本输入框 
- `int`: 数字输入框
- `float`: 浮点数输入框
- `bool`: 开关按钮
- `object`: 嵌套配置对象
- `list`: 列表 (暂未详细说明)

## 配置选项
- `description`: 配置项描述
- `hint`: 提示信息 (鼠标悬停显示)
- `obvious_hint`: 醒目显示提示
- `default`: 默认值
- `items`: object类型的子配置项
- `invisible`: 隐藏此配置项
- `options`: 下拉选项列表
- `editor_mode`: 启用代码编辑器 (v3.5.10+)
- `editor_language`: 代码语言 (默认json)
- `editor_theme`: 编辑器主题 (vs-light/vs-dark)

## 在插件中使用配置
```python
from astrbot.api import AstrBotConfig

@register("my_plugin", "author", "描述", "1.0.0")
class MyPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        
        # 读取配置
        self.api_key = config.get("api_key", "")
        self.max_retries = config.get("max_retries", 3)
        self.debug = config.get("enable_debug", False)
        
        # 读取嵌套配置
        server_config = config.get("server_config", {})
        self.host = server_config.get("host", "localhost")
        self.port = server_config.get("port", 8080)
        
        logger.info(f"插件配置: API密钥{'已设置' if self.api_key else '未设置'}")

    @filter.command("show_config")
    async def show_config(self, event: AstrMessageEvent):
        """显示当前配置"""
        config_info = f"""当前配置:
API密钥: {'已设置' if self.config.get('api_key') else '未设置'}
最大重试: {self.config.get('max_retries', 3)}
调试模式: {self.config.get('enable_debug', False)}
服务器: {self.host}:{self.port}"""
        yield event.plain_result(config_info)

    @filter.command("update_config")
    async def update_config(self, event: AstrMessageEvent, key: str, value: str):
        """更新配置"""
        try:
            # 根据key类型转换value
            if key == "max_retries":
                self.config[key] = int(value)
            elif key == "enable_debug":
                self.config[key] = value.lower() in ['true', '1', 'yes']
            else:
                self.config[key] = value
            
            # 保存配置
            self.config.save_config()
            yield event.plain_result(f"配置已更新: {key} = {value}")
            
        except Exception as e:
            yield event.plain_result(f"配置更新失败: {str(e)}")
```

## 无配置插件
```python
# 如果不需要配置，__init__ 只接收 context
@register("simple_plugin", "author", "描述", "1.0.0")
class SimplePlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
```

## 获取AstrBot全局配置
```python
@filter.command("global_config")
async def global_config(self, event: AstrMessageEvent):
    """获取AstrBot全局配置"""
    global_config = self.context.get_config()
    
    # 获取提供商配置
    provider_config = global_config.get('provider', {})
    
    # 获取平台配置
    platform_config = global_config.get('platform', {})
    
    yield event.plain_result("全局配置已获取")
```

## 配置验证示例
```python
def __init__(self, context: Context, config: AstrBotConfig):
    super().__init__(context)
    self.config = config
    
    # 验证必需配置
    required_keys = ['api_key', 'server_url']
    missing_keys = [key for key in required_keys if not config.get(key)]
    
    if missing_keys:
        logger.error(f"缺少必需配置: {missing_keys}")
        raise ValueError(f"缺少必需配置: {missing_keys}")
    
    # 验证配置格式
    max_retries = config.get('max_retries', 3)
    if not isinstance(max_retries, int) or max_retries < 1:
        logger.warning("max_retries配置无效，使用默认值3")
        config['max_retries'] = 3
        config.save_config()
```

## 动态配置更新
```python
@filter.command("reload_config")
@filter.permission_type(filter.PermissionType.ADMIN)
async def reload_config(self, event: AstrMessageEvent):
    """重新加载配置"""
    try:
        # 重新读取配置
        self.api_key = self.config.get("api_key", "")
        self.max_retries = self.config.get("max_retries", 3)
        
        # 重新初始化相关组件
        self.init_api_client()
        
        yield event.plain_result("配置已重新加载")
        
    except Exception as e:
        logger.error(f"重新加载配置失败: {e}")
        yield event.plain_result("配置重新加载失败")
```
