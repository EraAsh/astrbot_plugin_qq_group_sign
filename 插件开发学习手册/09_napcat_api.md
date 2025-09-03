# NapCat API 快速参考

## 基础调用方法
```python
# 检查是否为aiocqhttp平台
if event.get_platform_name() == "aiocqhttp":
    from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
    
    if isinstance(event, AiocqhttpMessageEvent):
        client = event.bot
        
        # 调用API
        result = await client.api.call_action('api_name', **parameters)
```

## API 接口分类表

### 🔄 消息相关 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `send_private_msg` | 发送私聊消息 | user_id, message |
| `send_group_msg` | 发送群消息 | group_id, message |
| `send_msg` | 发送消息(自动判断) | message_type, user_id/group_id, message |
| `delete_msg` | 撤回消息 | message_id |
| `get_msg` | 获取消息 | message_id |
| `get_forward_msg` | 获取合并转发消息 | id |
| `send_like` | 发送好友赞 | user_id, times |
| `set_msg_emoji_like` | 设置消息表情回应 | message_id, emoji_id |

### 👥 群组管理 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `get_group_info` | 获取群信息 | group_id, no_cache |
| `get_group_list` | 获取群列表 | - |
| `get_group_member_info` | 获取群成员信息 | group_id, user_id, no_cache |
| `get_group_member_list` | 获取群成员列表 | group_id |
| `set_group_kick` | 踢出群成员 | group_id, user_id, reject_add_request |
| `set_group_ban` | 群组单人禁言 | group_id, user_id, duration |
| `set_group_whole_ban` | 群组全员禁言 | group_id, enable |
| `set_group_admin` | 群组设置管理员 | group_id, user_id, enable |
| `set_group_card` | 设置群名片 | group_id, user_id, card |
| `set_group_name` | 设置群名 | group_id, group_name |
| `set_group_leave` | 退出群组 | group_id, is_dismiss |
| `set_group_special_title` | 设置群组专属头衔 | group_id, user_id, special_title, duration |

### 👤 好友管理 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `get_friend_list` | 获取好友列表 | - |
| `get_stranger_info` | 获取陌生人信息 | user_id, no_cache |
| `delete_friend` | 删除好友 | user_id |
| `set_friend_remark` | 设置好友备注 | user_id, remark |

### 📝 请求处理 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `set_friend_add_request` | 处理加好友请求 | flag, approve, remark |
| `set_group_add_request` | 处理加群请求/邀请 | flag, sub_type, approve, reason |

### 📁 文件操作 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `get_group_root_files` | 获取群根目录文件列表 | group_id |
| `get_group_files_by_folder` | 获取群子目录文件列表 | group_id, folder_id |
| `get_group_file_url` | 获取群文件下载链接 | group_id, file_id, busid |
| `upload_group_file` | 上传群文件 | group_id, file, name, folder |
| `delete_group_file` | 删除群文件 | group_id, file_id, busid |
| `upload_private_file` | 上传私聊文件 | user_id, file, name |

### ⚙️ 系统状态 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `get_login_info` | 获取登录号信息 | - |
| `get_status` | 获取运行状态 | - |
| `get_version_info` | 获取版本信息 | - |
| `set_restart` | 重启 | delay |
| `clean_cache` | 清理缓存 | - |

### 🎯 设置状态 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `set_online_status` | 设置在线状态 | status, ext_status, battery_status |
| `set_signature` | 设置个性签名 | signature |
| `set_model_show` | 设置机型显示 | model, model_show |
| `set_qq_avatar` | 设置QQ头像 | file |

### 🔍 其他实用 API
| API名称 | 功能 | 参数 |
|---------|------|------|
| `get_image` | 获取图片信息 | file |
| `can_send_image` | 检查是否可以发送图片 | - |
| `can_send_record` | 检查是否可以发送语音 | - |
| `get_record` | 获取语音 | file, out_format |
| `ocr_image` | 图片OCR | image |
| `get_group_honor_info` | 获取群荣誉信息 | group_id, type |
| `get_cookies` | 获取Cookies | domain |
| `get_csrf_token` | 获取CSRF Token | - |
| `get_credentials` | 获取QQ相关接口凭证 | domain |

## 消息类型构建

### 文本消息
```python
message = "纯文本消息"
# 或者
message = [{"type": "text", "data": {"text": "文本内容"}}]
```

### 图片消息
```python
# 网络图片
message = [{"type": "image", "data": {"file": "https://example.com/image.jpg"}}]

# 本地图片
message = [{"type": "image", "data": {"file": "file:///C:/path/to/image.jpg"}}]

# Base64图片
message = [{"type": "image", "data": {"file": "base64://iVBORw0KGgoAAAANSUhEUgA..."}}]

# 带缓存控制的图片
message = [{"type": "image", "data": {
    "file": "https://example.com/image.jpg",
    "cache": 0,  # 0不缓存，1缓存
    "proxy": 1,  # 0不走代理，1走代理
    "timeout": 30  # 超时时间
}}]
```

### 语音消息
```python
# 网络语音
message = [{"type": "record", "data": {"file": "https://example.com/voice.amr"}}]

# 本地语音
message = [{"type": "record", "data": {"file": "file:///C:/path/to/voice.wav"}}]

# 带参数的语音
message = [{"type": "record", "data": {
    "file": "voice.wav",
    "magic": 1,  # 变声效果
    "cache": 0
}}]
```

### 视频消息
```python
# 发送视频（仅群聊支持）
message = [{"type": "video", "data": {
    "file": "https://example.com/video.mp4",
    "cover": "https://example.com/cover.jpg"  # 封面图片（可选）
}}]
```

### AT消息
```python
# AT单个用户
message = [
    {"type": "at", "data": {"qq": "123456789"}},
    {"type": "text", "data": {"text": " 你好"}}
]

# AT全体成员
message = [
    {"type": "at", "data": {"qq": "all"}},
    {"type": "text", "data": {"text": " 大家好"}}
]
```

### 表情消息
```python
# QQ表情
message = [{"type": "face", "data": {"id": "123"}}]

# 系统表情
message = [{"type": "sface", "data": {"id": "123"}}]

# emoji表情
message = [{"type": "text", "data": {"text": "😀😃😄"}}]
```

### 合并转发消息
```python
# 构建转发消息节点
nodes = [
    {
        "type": "node",
        "data": {
            "name": "发送者1",
            "uin": "123456789",
            "content": [{"type": "text", "data": {"text": "第一条消息"}}]
        }
    },
    {
        "type": "node", 
        "data": {
            "name": "发送者2",
            "uin": "987654321",
            "content": [{"type": "text", "data": {"text": "第二条消息"}}]
        }
    }
]

# 发送合并转发
await client.api.call_action('send_group_forward_msg',
    group_id=int(event.get_group_id()),
    messages=nodes
)
```

### 回复消息
```python
# 回复指定消息
message = [
    {"type": "reply", "data": {"id": event.message_obj.message_id}},
    {"type": "text", "data": {"text": "这是回复内容"}}
]
```

### 戳一戳消息
```python
# 发送戳一戳
message = [{"type": "poke", "data": {"type": "1", "id": "123456789"}}]
```

### 分享消息
```python
# 分享链接
message = [{"type": "share", "data": {
    "url": "https://example.com",
    "title": "分享标题",
    "content": "分享描述",
    "image": "https://example.com/image.jpg"
}}]

# 分享音乐
message = [{"type": "music", "data": {
    "type": "163",  # 163网易云音乐, qq QQ音乐, xm 虾米音乐
    "id": "28949129"  # 歌曲ID
}}]

# 自定义音乐分享
message = [{"type": "music", "data": {
    "type": "custom",
    "url": "https://music.example.com/play",
    "audio": "https://music.example.com/audio.mp3",
    "title": "歌曲标题",
    "content": "歌手名",
    "image": "https://music.example.com/cover.jpg"
}}]
```

### 位置消息
```python
# 发送位置
message = [{"type": "location", "data": {
    "lat": "39.908722",  # 纬度
    "lon": "116.397499", # 经度  
    "title": "位置名称",
    "content": "位置描述"
}}]
```

### 红包消息
```python
# 发送红包（仅部分版本支持）
message = [{"type": "hb", "data": {"title": "恭喜发财"}}]
```

### 骰子和猜拳
```python
# 投骰子
message = [{"type": "dice", "data": {}}]

# 猜拳
message = [{"type": "rps", "data": {}}]
```

### 混合消息示例
```python
# 复杂混合消息
message = [
    {"type": "at", "data": {"qq": "123456789"}},
    {"type": "text", "data": {"text": " 看看这张图片："}},
    {"type": "image", "data": {"file": "https://example.com/image.jpg"}},
    {"type": "text", "data": {"text": "\n链接分享："}},
    {"type": "share", "data": {
        "url": "https://example.com",
        "title": "有趣的网站",
        "content": "快来看看这个网站"
    }}
]

await client.api.call_action('send_group_msg',
    group_id=int(event.get_group_id()),
    message=message
)
```
## 发送消息 API 详解

### 基础发送消息
```python
# 发送私聊消息
await client.api.call_action('send_private_msg', 
    user_id=123456789,
    message="消息内容"
)

# 发送群消息
await client.api.call_action('send_group_msg',
    group_id=123456789,
    message="消息内容"
)

# 通用发送消息（自动判断类型）
await client.api.call_action('send_msg',
    message_type="group",  # "private" 或 "group"
    group_id=123456789,    # 群消息时必需
    user_id=123456789,     # 私聊消息时必需
    message="消息内容"
)

# 发送临时会话消息
await client.api.call_action('send_private_msg',
    user_id=123456789,
    group_id=987654321,  # 指定群号发送临时会话
    message="临时会话内容"
)
```

### 合并转发消息
```python
# 发送群合并转发
await client.api.call_action('send_group_forward_msg',
    group_id=123456789,
    messages=[
        {
            "type": "node",
            "data": {
                "name": "发送者名称",
                "uin": "123456789",
                "content": "消息内容"
            }
        }
    ]
)

# 发送私聊合并转发
await client.api.call_action('send_private_forward_msg',
    user_id=123456789,
    messages=[...]
)
```

### 撤回消息
```python
await client.api.call_action('delete_msg',
    message_id=event.message_obj.message_id
)
```

### 获取消息
```python
msg_info = await client.api.call_action('get_msg',
    message_id="消息ID"
)
```

## 群管理API

### 获取群信息
```python
# 获取群信息
group_info = await client.api.call_action('get_group_info',
    group_id=int(event.get_group_id()),
    no_cache=False
)

# 获取群成员列表
members = await client.api.call_action('get_group_member_list',
    group_id=int(event.get_group_id())
)

# 获取群成员信息
member_info = await client.api.call_action('get_group_member_info',
    group_id=int(event.get_group_id()),
    user_id=123456789,
    no_cache=False
)
```

### 群成员管理
```python
# 禁言用户
await client.api.call_action('set_group_ban',
    group_id=int(event.get_group_id()),
    user_id=int(user_id),
    duration=600  # 禁言10分钟
)

# 解除禁言
await client.api.call_action('set_group_ban',
    group_id=int(event.get_group_id()),
    user_id=int(user_id),
    duration=0
)

# 踢出群成员
await client.api.call_action('set_group_kick',
    group_id=int(event.get_group_id()),
    user_id=int(user_id),
    reject_add_request=False
)

# 设置群名片
await client.api.call_action('set_group_card',
    group_id=int(event.get_group_id()),
    user_id=int(user_id),
    card="新群名片"
)

# 设置管理员
await client.api.call_action('set_group_admin',
    group_id=int(event.get_group_id()),
    user_id=int(user_id),
    enable=True  # True设置，False取消
)
```

### 全群操作
```python
# 全群禁言
await client.api.call_action('set_group_whole_ban',
    group_id=int(event.get_group_id()),
    enable=True
)

# 设置群名
await client.api.call_action('set_group_name',
    group_id=int(event.get_group_id()),
    group_name="新群名"
)

# 退出群聊
await client.api.call_action('set_group_leave',
    group_id=int(event.get_group_id()),
    is_dismiss=False  # True为解散群（仅群主）
)
```

## 好友操作API

### 好友信息
```python
# 获取好友列表
friends = await client.api.call_action('get_friend_list')

# 获取账号信息
account_info = await client.api.call_action('get_login_info')
```

### 好友管理
```python
# 点赞
await client.api.call_action('send_like',
    user_id=int(event.get_sender_id()),
    times=10  # 1-10次
)

# 设置好友备注
await client.api.call_action('set_friend_remark',
    user_id=123456789,
    remark="新备注"
)

# 删除好友
await client.api.call_action('delete_friend',
    user_id=123456789
)

# 处理好友请求
await client.api.call_action('set_friend_add_request',
    flag="请求标识",
    approve=True,  # True同意，False拒绝
    remark="备注"
)
```

## 文件操作API

### 群文件
```python
# 获取群根目录文件
files = await client.api.call_action('get_group_root_files',
    group_id=int(event.get_group_id())
)

# 上传群文件
await client.api.call_action('upload_group_file',
    group_id=int(event.get_group_id()),
    file="/path/to/file",
    name="文件名.txt"
)

# 删除群文件
await client.api.call_action('delete_group_file',
    group_id=int(event.get_group_id()),
    file_id="文件ID",
    busid=102
)

# 获取群文件下载链接
file_url = await client.api.call_action('get_group_file_url',
    group_id=int(event.get_group_id()),
    file_id="文件ID",
    busid=102
)
```

### 私聊文件
```python
# 上传私聊文件
await client.api.call_action('upload_private_file',
    user_id=int(event.get_sender_id()),
    file="/path/to/file",
    name="文件名.txt"
)
```

## 状态和系统API

### 获取状态
```python
# 获取机器人状态
status = await client.api.call_action('get_status')

# 获取版本信息
version = await client.api.call_action('get_version_info')

# 获取登录账号信息
login_info = await client.api.call_action('get_login_info')
```

### 设置状态
```python
# 设置在线状态
await client.api.call_action('set_online_status',
    status=10,  # 10在线，20离开，30隐身，40忙碌
    ext_status=0,
    battery_status=1
)

# 设置个性签名
await client.api.call_action('set_signature',
    signature="我的个性签名"
)
```

## 实用封装类
```python
class NapCatHelper:
    def __init__(self, client):
        self.client = client
    
    async def safe_call(self, action: str, **params):
        """安全的API调用"""
        try:
            return await self.client.api.call_action(action, **params)
        except Exception as e:
            logger.error(f"API调用失败 {action}: {e}")
            return None
    
    async def ban_user(self, group_id: int, user_id: int, duration: int = 600):
        """禁言用户"""
        return await self.safe_call('set_group_ban',
            group_id=group_id,
            user_id=user_id,
            duration=max(60, min(duration, 2592000))  # 限制1分钟到30天
        )
    
    async def get_group_members(self, group_id: int):
        """获取群成员列表"""
        result = await self.safe_call('get_group_member_list', group_id=group_id)
        return result.get('data', []) if result else []
    
    async def send_group_message(self, group_id: int, message):
        """发送群消息"""
        return await self.safe_call('send_group_msg',
            group_id=group_id,
            message=message
        )
    
    async def is_admin(self, group_id: int, user_id: int):
        """检查用户是否为管理员"""
        member_info = await self.safe_call('get_group_member_info',
            group_id=group_id,
            user_id=user_id
        )
        if member_info and 'data' in member_info:
            role = member_info['data'].get('role', 'member')
            return role in ['admin', 'owner']
        return False

# 使用示例
def __init__(self, context: Context):
    super().__init__(context)
    self.napcat_helper = None

@filter.command("helper_ban")
async def helper_ban(self, event: AstrMessageEvent, duration: int = 600):
    """使用辅助类禁言"""
    if event.get_platform_name() == "aiocqhttp" and event.get_group_id():
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            if not self.napcat_helper:
                self.napcat_helper = NapCatHelper(event.bot)
            
            # 查找AT的用户
            at_user = None
            for msg_seg in event.message_obj.message:
                if hasattr(msg_seg, 'type') and msg_seg.type == 'at':
                    at_user = msg_seg.data.get('qq')
                    break
            
            if at_user:
                result = await self.napcat_helper.ban_user(
                    int(event.get_group_id()),
                    int(at_user),
                    duration
                )
                if result:
                    yield event.plain_result(f"已禁言用户 {duration} 秒")
                else:
                    yield event.plain_result("禁言失败")
            else:
                yield event.plain_result("请AT要禁言的用户")
```

## 错误处理
```python
async def safe_napcat_call(self, event, action: str, **params):
    """安全的NapCat API调用"""
    try:
        if event.get_platform_name() != "aiocqhttp":
            return None
            
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            result = await event.bot.api.call_action(action, **params)
            return result
            
    except Exception as e:
        logger.error(f"NapCat API调用失败 {action}: {e}")
        return None

# 使用示例
@filter.command("safe_delete")
async def safe_delete(self, event: AstrMessageEvent):
    """安全删除消息"""
    result = await self.safe_napcat_call(event, 'delete_msg',
        message_id=event.message_obj.message_id
    )
    
    if result:
        yield event.plain_result("消息已删除")
    else:
        yield event.plain_result("删除失败或不支持此操作")
```

## 获取AT用户的辅助函数
```python
def get_at_users(self, event: AstrMessageEvent) -> list:
    """获取消息中AT的所有用户ID"""
    at_users = []
    for msg_seg in event.message_obj.message:
        if hasattr(msg_seg, 'type') and msg_seg.type == 'at':
            qq = msg_seg.data.get('qq')
            if qq and qq != 'all':  # 排除@全体成员
                at_users.append(qq)
    return at_users

def get_first_at_user(self, event: AstrMessageEvent) -> str:
    """获取第一个AT的用户ID"""
    at_users = self.get_at_users(event)
    return at_users[0] if at_users else None
```

## 权限检查辅助
```python
async def check_bot_admin(self, event: AstrMessageEvent) -> bool:
    """检查机器人是否为管理员"""
    if not event.get_group_id():
        return False
        
    if event.get_platform_name() == "aiocqhttp":
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            try:
                # 获取机器人自己的群成员信息
                bot_info = await event.bot.api.call_action('get_group_member_info',
                    group_id=int(event.get_group_id()),
                    user_id=int(event.message_obj.self_id)
                )
                
                if bot_info and 'data' in bot_info:
                    role = bot_info['data'].get('role', 'member')
                    return role in ['admin', 'owner']
                    
            except Exception as e:
                logger.error(f"检查机器人权限失败: {e}")
    
## NapCat 特有 API

### 获取群荣誉信息
```python
# 获取群龙王
honor_info = await client.api.call_action('get_group_honor_info',
    group_id=int(event.get_group_id()),
    type="talkative"  # 龙王
)

# 获取群群聊之火  
honor_info = await client.api.call_action('get_group_honor_info',
    group_id=int(event.get_group_id()),
    type="performer"  # 群聊之火
)

# 获取群快乐源泉
honor_info = await client.api.call_action('get_group_honor_info',
    group_id=int(event.get_group_id()),
    type="emotion"  # 快乐源泉
)

# 获取所有荣誉
honor_info = await client.api.call_action('get_group_honor_info',
    group_id=int(event.get_group_id()),
    type="all"
)
```

### 图片 OCR 识别
```python
# OCR识别图片中的文字
ocr_result = await client.api.call_action('ocr_image',
    image="https://example.com/image.jpg"  # 支持URL、本地路径、base64
)

# 处理OCR结果
if ocr_result and ocr_result.get('data'):
    texts = ocr_result['data'].get('texts', [])
    for text_info in texts:
        text = text_info.get('text', '')
        confidence = text_info.get('confidence', 0)
        print(f"识别文字: {text}, 置信度: {confidence}")
```

### 获取群文件系统信息
```python
# 获取群文件系统信息
file_system_info = await client.api.call_action('get_group_file_system_info',
    group_id=int(event.get_group_id())
)

# 获取群根目录文件
root_files = await client.api.call_action('get_group_root_files',
    group_id=int(event.get_group_id())
)

# 获取群子目录文件
folder_files = await client.api.call_action('get_group_files_by_folder',
    group_id=int(event.get_group_id()),
    folder_id="folder_id_here"
)

# 创建群文件夹
await client.api.call_action('create_group_file_folder',
    group_id=int(event.get_group_id()),
    name="新文件夹",
    parent_id="/"  # 父目录ID，根目录为"/"
)

# 删除群文件夹
await client.api.call_action('delete_group_folder',
    group_id=int(event.get_group_id()),
    folder_id="folder_id_here"
)

# 重命名群文件夹
await client.api.call_action('rename_group_folder',
    group_id=int(event.get_group_id()),
    folder_id="folder_id_here",
    new_name="新文件夹名"
)
```

### 获取网络相关信息
```python
# 获取Cookies（用于访问QQ空间等）
cookies = await client.api.call_action('get_cookies',
    domain="qzone.qq.com"
)

# 获取CSRF Token
csrf_token = await client.api.call_action('get_csrf_token')

# 获取QQ相关接口凭证
credentials = await client.api.call_action('get_credentials',
    domain="qzone.qq.com"
)
```

### 获取历史消息记录
```python
# 获取群聊天记录
history = await client.api.call_action('get_group_msg_history',
    group_id=int(event.get_group_id()),
    message_seq=0  # 起始消息序号，0为最新消息
)

# 获取好友聊天记录  
history = await client.api.call_action('get_friend_msg_history',
    user_id=int(event.get_sender_id()),
    message_seq=0
)
```

### 设置群头像
```python
# 设置群头像（需要群主权限）
await client.api.call_action('set_group_portrait',
    group_id=int(event.get_group_id()),
    file="file:///C:/path/to/avatar.jpg",  # 支持本地文件、URL、base64
    cache=1
)
```

### 群公告管理
```python
# 发布群公告
await client.api.call_action('_send_group_notice',
    group_id=int(event.get_group_id()),
    content="公告内容",
    image=""  # 可选图片
)

# 获取群公告列表
notices = await client.api.call_action('_get_group_notice',
    group_id=int(event.get_group_id())
)
```

### 处理群邀请和申请
```python
# 处理加群请求
await client.api.call_action('set_group_add_request',
    flag="request_flag",  # 请求标识
    sub_type="add",       # "add"加群申请, "invite"群邀请
    approve=True,         # True同意，False拒绝
    reason="拒绝理由"      # 拒绝时的理由
)
```

### 消息表情回应
```python
# 给消息添加表情回应（仅部分版本支持）
await client.api.call_action('set_msg_emoji_like',
    message_id=event.message_obj.message_id,
    emoji_id="128077"  # 表情ID，如128077是👍
)
```

## 高级功能封装

### 智能消息发送器
```python
class SmartMessageSender:
    def __init__(self, client):
        self.client = client
    
    async def send_auto(self, event: AstrMessageEvent, content, **kwargs):
        """自动判断发送类型的智能发送"""
        try:
            if event.get_group_id():
                # 群消息
                return await self.client.api.call_action('send_group_msg',
                    group_id=int(event.get_group_id()),
                    message=content,
                    **kwargs
                )
            else:
                # 私聊消息
                return await self.client.api.call_action('send_private_msg',
                    user_id=int(event.get_sender_id()),
                    message=content,
                    **kwargs
                )
        except Exception as e:
            logger.error(f"发送消息失败: {e}")
            return None
    
    async def send_with_retry(self, event: AstrMessageEvent, content, max_retries=3):
        """带重试的消息发送"""
        for attempt in range(max_retries):
            try:
                result = await self.send_auto(event, content)
                if result:
                    return result
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"消息发送失败，已重试{max_retries}次: {e}")
                    raise
                await asyncio.sleep(1)  # 等待1秒后重试
        return None
    
    async def send_long_text(self, event: AstrMessageEvent, text: str, max_length: int = 4000):
        """发送长文本（自动分段）"""
        if len(text) <= max_length:
            return await self.send_auto(event, text)
        
        # 按行分割并重组
        lines = text.split('\n')
        current_chunk = ""
        results = []
        
        for line in lines:
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += (line + '\n')
            else:
                if current_chunk:
                    results.append(await self.send_auto(event, current_chunk.strip()))
                current_chunk = line + '\n'
        
        if current_chunk:
            results.append(await self.send_auto(event, current_chunk.strip()))
        
        return results
    
    async def send_image_with_text(self, event: AstrMessageEvent, image_url: str, text: str = ""):
        """发送图片+文字"""
        message = []
        if text:
            message.append({"type": "text", "data": {"text": text}})
        message.append({"type": "image", "data": {"file": image_url}})
        
        return await self.send_auto(event, message)

# 使用示例
def __init__(self, context: Context):
    super().__init__(context)
    self.smart_sender = None

@filter.command("smart_send")
async def smart_send(self, event: AstrMessageEvent, content: str):
    """智能发送演示"""
    if event.get_platform_name() == "aiocqhttp":
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            if not self.smart_sender:
                self.smart_sender = SmartMessageSender(event.bot)
            
            result = await self.smart_sender.send_with_retry(event, content)
            if result:
                yield event.plain_result("消息发送成功")
            else:
                yield event.plain_result("消息发送失败")
```

### 完整的群管理助手
```python
class GroupManager:
    def __init__(self, client):
        self.client = client
    
    async def get_member_role(self, group_id: int, user_id: int):
        """获取成员身份"""
        try:
            member_info = await self.client.api.call_action('get_group_member_info',
                group_id=group_id,
                user_id=user_id
            )
            return member_info.get('data', {}).get('role', 'member')
        except:
            return 'member'
    
    async def is_admin_or_owner(self, group_id: int, user_id: int):
        """检查是否为管理员或群主"""
        role = await self.get_member_role(group_id, user_id)
        return role in ['admin', 'owner']
    
    async def batch_ban(self, group_id: int, user_ids: list, duration: int = 600):
        """批量禁言"""
        results = []
        for user_id in user_ids:
            try:
                result = await self.client.api.call_action('set_group_ban',
                    group_id=group_id,
                    user_id=user_id,
                    duration=duration
                )
                results.append((user_id, True, result))
            except Exception as e:
                results.append((user_id, False, str(e)))
        return results
    
    async def clean_inactive_members(self, group_id: int, days_threshold: int = 30):
        """清理不活跃成员（仅返回列表，不执行踢出）"""
        try:
            members = await self.client.api.call_action('get_group_member_list',
                group_id=group_id
            )
            
            if not members or 'data' not in members:
                return []
            
            import time
            current_time = time.time()
            inactive_members = []
            
            for member in members['data']:
                last_sent_time = member.get('last_sent_time', 0)
                if current_time - last_sent_time > days_threshold * 24 * 3600:
                    if member.get('role') == 'member':  # 只考虑普通成员
                        inactive_members.append({
                            'user_id': member.get('user_id'),
                            'nickname': member.get('nickname', ''),
                            'card': member.get('card', ''),
                            'last_sent_time': last_sent_time
                        })
            
            return inactive_members
        except Exception as e:
            logger.error(f"获取不活跃成员失败: {e}")
            return []
    
    async def get_group_stats(self, group_id: int):
        """获取群统计信息"""
        try:
            group_info = await self.client.api.call_action('get_group_info',
                group_id=group_id
            )
            members = await self.client.api.call_action('get_group_member_list',
                group_id=group_id
            )
            
            if not (group_info and members):
                return None
            
            group_data = group_info.get('data', {})
            members_data = members.get('data', [])
            
            # 统计身份分布
            role_count = {'owner': 0, 'admin': 0, 'member': 0}
            for member in members_data:
                role = member.get('role', 'member')
                role_count[role] += 1
            
            return {
                'group_name': group_data.get('group_name', ''),
                'member_count': group_data.get('member_count', 0),
                'max_member_count': group_data.get('max_member_count', 0),
                'role_distribution': role_count,
                'group_level': group_data.get('group_level', 0)
            }
        except Exception as e:
            logger.error(f"获取群统计失败: {e}")
            return None

# 使用示例
@filter.command("group_stats")
async def group_stats(self, event: AstrMessageEvent):
    """群统计信息"""
    if not event.get_group_id():
        yield event.plain_result("此命令仅在群聊中可用")
        return
    
    if event.get_platform_name() == "aiocqhttp":
        from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
        
        if isinstance(event, AiocqhttpMessageEvent):
            manager = GroupManager(event.bot)
            stats = await manager.get_group_stats(int(event.get_group_id()))
            
            if stats:
                result = f"""群统计信息:
📝 群名: {stats['group_name']}
👥 人数: {stats['member_count']}/{stats['max_member_count']}
👑 群主: {stats['role_distribution']['owner']}人
🛡️ 管理: {stats['role_distribution']['admin']}人  
👤 成员: {stats['role_distribution']['member']}人
⭐ 等级: {stats['group_level']}"""
                
                yield event.plain_result(result)
            else:
                yield event.plain_result("获取群信息失败")
```
