# 消息处理快速参考

## 基础消息发送
```python
# 纯文本
yield event.plain_result("文本消息")

# 图片
yield event.image_result("path/to/image.jpg")
yield event.image_result("https://example.com/image.jpg")

# 消息链
chain = [Comp.Plain("文本"), Comp.Image.fromURL("url")]
yield event.chain_result(chain)
```

## 获取消息信息
```python
# 基本信息
sender_name = event.get_sender_name()      # 发送者名称
sender_id = event.get_sender_id()          # 发送者ID
group_id = event.get_group_id()            # 群组ID (可能为空)
platform_name = event.get_platform_name() # 平台名称
message_str = event.message_str            # 纯文本内容
unified_msg_origin = event.unified_msg_origin # 统一消息来源

# 消息对象
message_obj = event.message_obj            # AstrBotMessage对象
raw_message = event.message_obj.raw_message # 平台原始消息
message_chain = event.message_obj.message  # 消息链
```

## 消息组件 (导入: import astrbot.api.message_components as Comp)
```python
# 文本
Comp.Plain("文本内容")

# 图片
Comp.Image.fromURL("https://example.com/image.jpg")
Comp.Image.fromFileSystem("path/to/image.jpg")

# At用户
Comp.At(qq=user_id)

# 语音 (WAV格式)
Comp.Record(file="path/to/record.wav")

# 视频
Comp.Video.fromFileSystem("path/to/video.mp4")
Comp.Video.fromURL("https://example.com/video.mp4")

# 文件
Comp.File(file="path/to/file.txt", name="file.txt")

# QQ表情 (仅aiocqhttp)
Comp.Face(id=21)

# 回复消息
Comp.Reply(id="message_id")

# 合并转发节点 (仅aiocqhttp)
Comp.Node(uin=user_id, name="发送者", content=[Comp.Plain("内容")])
```

## 富媒体消息示例
```python
@filter.command("rich")
async def rich_message(self, event: AstrMessageEvent):
    chain = [
        Comp.At(qq=event.get_sender_id()),
        Comp.Plain(" 看这张图片: "),
        Comp.Image.fromURL("https://example.com/image.jpg"),
        Comp.Plain("\n还有视频: "),
        Comp.Video.fromURL("https://example.com/video.mp4")
    ]
    yield event.chain_result(chain)
```

## 主动发送消息
```python
from astrbot.api.event import MessageChain

# 保存会话ID
umo = event.unified_msg_origin

# 稍后发送
message_chain = MessageChain().message("Hello!").file_image("path/to/image.jpg")
await self.context.send_message(umo, message_chain)
```

## 在会话控制中发送消息
```python
# 在 session_waiter 中不能使用 yield，必须用 send
@session_waiter(timeout=60)
async def waiter(controller: SessionController, event: AstrMessageEvent):
    result = event.make_result()
    result.chain = [Comp.Plain("会话消息")]
    await event.send(result)
```

## 平台兼容性快查
| 平台 | 文本 | 图片 | 语音 | 视频 | At | 合并转发 |
|------|------|------|------|------|-----|----------|
| QQ个人号 | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Telegram | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| QQ官方 | ❌ | ✅ | ✅ | ❌ | ❌ | ❌ |
| 飞书 | ✅ | ✅ | ✅ | ❌ | ❌ | ✅ |

## 消息类型检查
```python
# 检查消息中的图片
for msg_seg in event.message_obj.message:
    if hasattr(msg_seg, 'type') and msg_seg.type == 'image':
        image_url = msg_seg.data.get('url')
        # 处理图片

# 检查AT用户
at_users = []
for msg_seg in event.message_obj.message:
    if hasattr(msg_seg, 'type') and msg_seg.type == 'at':
        at_users.append(msg_seg.data.get('qq'))
```
