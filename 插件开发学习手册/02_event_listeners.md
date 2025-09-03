# 事件监听器快速参考

## 基础过滤器
```python
from astrbot.api.event import filter, AstrMessageEvent

# 简单指令
@filter.command("hello")
async def hello(self, event: AstrMessageEvent):
    yield event.plain_result("Hello!")

# 带参数指令
@filter.command("echo")
async def echo(self, event: AstrMessageEvent, message: str):
    yield event.plain_result(f"你说: {message}")

# 带类型参数
@filter.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    yield event.plain_result(f"结果: {a + b}")
```

## 指令组
```python
@filter.command_group("math")
def math(self):
    pass

@math.command("add")
async def add(self, event: AstrMessageEvent, a: int, b: int):
    # /math add 1 2
    yield event.plain_result(f"结果: {a + b}")
```

## 事件类型过滤
```python
# 私聊消息
@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
async def on_private(self, event: AstrMessageEvent):
    yield event.plain_result("私聊消息")

# 群聊消息
@filter.event_message_type(filter.EventMessageType.GROUP_MESSAGE)
async def on_group(self, event: AstrMessageEvent):
    yield event.plain_result("群聊消息")

# 所有消息
@filter.event_message_type(filter.EventMessageType.ALL)
async def on_all(self, event: AstrMessageEvent):
    yield event.plain_result("所有消息")
```

## 平台过滤
```python
# 指定平台
@filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
async def on_qq(self, event: AstrMessageEvent):
    yield event.plain_result("QQ平台消息")

# 多平台
@filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP | filter.PlatformAdapterType.TELEGRAM)
async def on_multiple(self, event: AstrMessageEvent):
    yield event.plain_result("QQ或Telegram消息")
```

## 权限控制
```python
# 仅管理员
@filter.permission_type(filter.PermissionType.ADMIN)
@filter.command("admin_cmd")
async def admin_cmd(self, event: AstrMessageEvent):
    yield event.plain_result("管理员指令")
```

## 组合过滤器
```python
@filter.command("private_admin")
@filter.event_message_type(filter.EventMessageType.PRIVATE_MESSAGE)
@filter.permission_type(filter.PermissionType.ADMIN)
async def private_admin(self, event: AstrMessageEvent):
    yield event.plain_result("私聊管理员指令")
```

## 优先级
```python
@filter.command("high_priority", priority=1)
async def high_priority(self, event: AstrMessageEvent):
    yield event.plain_result("高优先级")
```

## 指令别名
```python
@filter.command("help", alias={'帮助', 'helpme'})
async def help(self, event: AstrMessageEvent):
    yield event.plain_result("帮助信息")
```

## 事件钩子 (v3.4.34+)
```python
# AstrBot 初始化完成
@filter.on_astrbot_loaded()
async def on_loaded(self):
    logger.info("AstrBot 初始化完成")

# LLM 请求前
@filter.on_llm_request()
async def on_llm_request(self, event: AstrMessageEvent, req: ProviderRequest):
    req.system_prompt += "自定义提示"

# LLM 响应后
@filter.on_llm_response()
async def on_llm_response(self, event: AstrMessageEvent, resp: LLMResponse):
    logger.info(f"LLM响应: {resp}")

# 消息发送前
@filter.on_decorating_result()
async def on_decorating(self, event: AstrMessageEvent):
    result = event.get_result()
    result.chain.append(Comp.Plain("!"))

# 消息发送后
@filter.after_message_sent()
async def after_sent(self, event: AstrMessageEvent):
    logger.info("消息已发送")
```

## 控制事件传播
```python
@filter.command("stop")
async def stop_event(self, event: AstrMessageEvent):
    if not self.check():
        yield event.plain_result("检查失败")
        event.stop_event()  # 停止后续处理
```
