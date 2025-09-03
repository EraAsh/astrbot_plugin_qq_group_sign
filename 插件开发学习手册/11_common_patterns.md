# 常见模式和最佳实践快速参考

## 插件初始化模式
```python
# 标准初始化模式
class MyPlugin(BasePlugin):
    def __init__(self, context: Context):
        super().__init__(context)
        
        # 1. 插件信息
        self.plugin_info = PluginMetadata(
            plugin_name="my_plugin",
            plugin_type="function",
            author="Your Name",
            desc="插件描述",
            version="1.0.0",
        )
        
        # 2. 配置初始化
        self.config_schema = ConfigModel(
            api_key=ConfigItem(
                default="",
                description="API密钥",
                required=True
            )
        )
        
        # 3. 状态变量
        self.is_initialized = False
        self.cache = {}
        self.client = None
        
        # 4. 注册资源清理
        atexit.register(self.cleanup)
    
    async def info(self) -> PluginMetadata:
        return self.plugin_info
    
    async def initialize(self):
        """延迟初始化"""
        if self.is_initialized:
            return
        
        try:
            # 初始化外部客户端
            self.client = SomeAPIClient(self.config.api_key)
            await self.client.connect()
            
            self.is_initialized = True
            logger.info(f"{self.plugin_info.plugin_name} 初始化成功")
            
        except Exception as e:
            logger.error(f"插件初始化失败: {e}")
            raise
    
    def cleanup(self):
        """资源清理"""
        if self.client:
            self.client.close()
```

## 错误处理和日志模式
```python
import traceback
from typing import Optional

# 统一错误处理装饰器
def handle_errors(func):
    """错误处理装饰器"""
    async def wrapper(self, event: AstrMessageEvent, *args, **kwargs):
        try:
            async for result in func(self, event, *args, **kwargs):
                yield result
        except ValueError as e:
            logger.warning(f"参数错误: {e}")
            yield event.plain_result(f"参数错误: {str(e)}")
        except ConnectionError as e:
            logger.error(f"连接错误: {e}")
            yield event.plain_result("网络连接失败，请稍后重试")
        except Exception as e:
            logger.error(f"未知错误: {e}\n{traceback.format_exc()}")
            yield event.plain_result("处理失败，请查看日志")
    
    return wrapper

# 使用示例
@filter.command("api_call")
@handle_errors
async def api_call(self, event: AstrMessageEvent, query: str):
    """API调用示例"""
    if not query.strip():
        raise ValueError("查询内容不能为空")
    
    # 确保初始化
    await self.initialize()
    
    # API调用
    result = await self.client.query(query)
    yield event.plain_result(result)
```

## 配置管理模式
```python
from pydantic import BaseModel, Field
from typing import List, Dict, Optional

class APIConfig(BaseModel):
    """API配置子模块"""
    base_url: str = Field(default="https://api.example.com")
    timeout: int = Field(default=30, description="超时时间(秒)")
    max_retries: int = Field(default=3, description="最大重试次数")

class CacheConfig(BaseModel):
    """缓存配置子模块"""
    enable: bool = Field(default=True, description="启用缓存")
    ttl: int = Field(default=300, description="缓存过期时间(秒)")
    max_size: int = Field(default=1000, description="最大缓存条目")

class MyPluginConfig(BaseModel):
    """插件主配置"""
    api_key: str = Field(default="", description="API密钥")
    api: APIConfig = Field(default_factory=APIConfig)
    cache: CacheConfig = Field(default_factory=CacheConfig)
    allowed_users: List[str] = Field(default_factory=list, description="允许使用的用户ID")
    custom_commands: Dict[str, str] = Field(default_factory=dict, description="自定义命令")

# 配置使用
def __init__(self, context: Context):
    super().__init__(context)
    
    self.config_schema = ConfigModel(**{
        field.alias or name: ConfigItem(
            default=field.default,
            description=field.field_info.description or "",
            required=field.is_required()
        )
        for name, field in MyPluginConfig.__fields__.items()
    })

@property
def plugin_config(self) -> MyPluginConfig:
    """获取类型化配置"""
    return MyPluginConfig(**self.config)
```

## 权限控制模式
```python
from functools import wraps

class PermissionManager:
    def __init__(self, config):
        self.allowed_users = set(config.get('allowed_users', []))
        self.admin_users = set(config.get('admin_users', []))
        self.blocked_users = set(config.get('blocked_users', []))
    
    def check_permission(self, user_id: str, level: str = "user") -> bool:
        """检查权限"""
        if user_id in self.blocked_users:
            return False
        
        if level == "admin":
            return user_id in self.admin_users
        
        if self.allowed_users:  # 如果设置了白名单
            return user_id in self.allowed_users or user_id in self.admin_users
        
        return True  # 无白名单时允许所有用户

def require_permission(level: str = "user"):
    """权限检查装饰器"""
    def decorator(func):
        @wraps(func)
        async def wrapper(self, event: AstrMessageEvent, *args, **kwargs):
            user_id = event.get_sender_id()
            
            if not self.permission_manager.check_permission(user_id, level):
                yield event.plain_result("权限不足")
                return
            
            async for result in func(self, event, *args, **kwargs):
                yield result
        
        return wrapper
    return decorator

# 使用示例
@filter.command("admin_cmd")
@require_permission("admin")
async def admin_command(self, event: AstrMessageEvent):
    """管理员命令"""
    yield event.plain_result("执行管理员操作")
```

## 缓存管理模式
```python
import time
import asyncio
from typing import Any, Optional, Dict, Tuple

class TTLCache:
    """带过期时间的缓存"""
    def __init__(self, default_ttl: int = 300, max_size: int = 1000):
        self.cache: Dict[str, Tuple[Any, float]] = {}
        self.default_ttl = default_ttl
        self.max_size = max_size
        self.lock = asyncio.Lock()
    
    async def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        async with self.lock:
            if key in self.cache:
                value, expires_at = self.cache[key]
                if time.time() < expires_at:
                    return value
                else:
                    del self.cache[key]
            return None
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置缓存"""
        async with self.lock:
            # 清理过期缓存
            await self._cleanup_expired()
            
            # 如果超过最大大小，删除最旧的
            if len(self.cache) >= self.max_size:
                oldest_key = min(self.cache.keys(), 
                               key=lambda k: self.cache[k][1])
                del self.cache[oldest_key]
            
            ttl = ttl or self.default_ttl
            expires_at = time.time() + ttl
            self.cache[key] = (value, expires_at)
    
    async def _cleanup_expired(self):
        """清理过期缓存"""
        current_time = time.time()
        expired_keys = [
            key for key, (_, expires_at) in self.cache.items()
            if current_time >= expires_at
        ]
        for key in expired_keys:
            del self.cache[key]

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.cache = TTLCache(
        default_ttl=self.plugin_config.cache.ttl,
        max_size=self.plugin_config.cache.max_size
    )

@filter.command("cached_query")
async def cached_query(self, event: AstrMessageEvent, query: str):
    """带缓存的查询"""
    cache_key = f"query:{hash(query)}"
    
    # 尝试从缓存获取
    if self.plugin_config.cache.enable:
        cached_result = await self.cache.get(cache_key)
        if cached_result:
            yield event.plain_result(f"[缓存] {cached_result}")
            return
    
    # 执行实际查询
    result = await self.perform_query(query)
    
    # 存入缓存
    if self.plugin_config.cache.enable:
        await self.cache.set(cache_key, result)
    
    yield event.plain_result(result)
```

## 异步任务管理模式
```python
import asyncio
from typing import Set, Dict
from dataclasses import dataclass
from datetime import datetime

@dataclass
class TaskInfo:
    """任务信息"""
    task_id: str
    name: str
    created_at: datetime
    user_id: str
    task: asyncio.Task

class TaskManager:
    """异步任务管理器"""
    def __init__(self):
        self.tasks: Dict[str, TaskInfo] = {}
        self.user_tasks: Dict[str, Set[str]] = {}  # 用户->任务ID集合
        self.lock = asyncio.Lock()
    
    async def start_task(
        self, 
        task_id: str, 
        coro, 
        name: str, 
        user_id: str
    ) -> bool:
        """启动任务"""
        async with self.lock:
            if task_id in self.tasks:
                return False  # 任务已存在
            
            task = asyncio.create_task(coro)
            task_info = TaskInfo(
                task_id=task_id,
                name=name,
                created_at=datetime.now(),
                user_id=user_id,
                task=task
            )
            
            self.tasks[task_id] = task_info
            
            if user_id not in self.user_tasks:
                self.user_tasks[user_id] = set()
            self.user_tasks[user_id].add(task_id)
            
            # 任务完成时自动清理
            task.add_done_callback(lambda t: asyncio.create_task(self._cleanup_task(task_id)))
            
            return True
    
    async def cancel_task(self, task_id: str) -> bool:
        """取消任务"""
        async with self.lock:
            if task_id in self.tasks:
                task_info = self.tasks[task_id]
                task_info.task.cancel()
                return True
            return False
    
    async def get_user_tasks(self, user_id: str) -> List[TaskInfo]:
        """获取用户的任务"""
        async with self.lock:
            if user_id in self.user_tasks:
                return [
                    self.tasks[task_id] 
                    for task_id in self.user_tasks[user_id]
                    if task_id in self.tasks
                ]
            return []
    
    async def _cleanup_task(self, task_id: str):
        """清理完成的任务"""
        async with self.lock:
            if task_id in self.tasks:
                task_info = self.tasks[task_id]
                user_id = task_info.user_id
                
                del self.tasks[task_id]
                
                if user_id in self.user_tasks:
                    self.user_tasks[user_id].discard(task_id)
                    if not self.user_tasks[user_id]:
                        del self.user_tasks[user_id]

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.task_manager = TaskManager()

@filter.command("long_task")
async def start_long_task(self, event: AstrMessageEvent, duration: int = 10):
    """启动长时间任务"""
    user_id = event.get_sender_id()
    task_id = f"long_task_{user_id}_{int(time.time())}"
    
    async def long_running_task():
        """长时间运行的任务"""
        try:
            for i in range(duration):
                await asyncio.sleep(1)
                logger.info(f"任务进度: {i+1}/{duration}")
            
            # 任务完成后发送消息
            await self.send_message(
                event.get_chat_id(),
                f"长时间任务完成！耗时 {duration} 秒"
            )
            
        except asyncio.CancelledError:
            logger.info(f"任务 {task_id} 被取消")
            await self.send_message(
                event.get_chat_id(),
                "任务已被取消"
            )
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            await self.send_message(
                event.get_chat_id(),
                f"任务执行失败: {str(e)}"
            )
    
    success = await self.task_manager.start_task(
        task_id, long_running_task(), "长时间任务", user_id
    )
    
    if success:
        yield event.plain_result(f"任务已启动，ID: {task_id}")
    else:
        yield event.plain_result("任务启动失败，可能已存在同名任务")

@filter.command("cancel_task")
async def cancel_task(self, event: AstrMessageEvent, task_id: str):
    """取消任务"""
    success = await self.task_manager.cancel_task(task_id)
    if success:
        yield event.plain_result(f"任务 {task_id} 已取消")
    else:
        yield event.plain_result("任务不存在或已完成")

@filter.command("my_tasks")
async def list_my_tasks(self, event: AstrMessageEvent):
    """查看我的任务"""
    user_id = event.get_sender_id()
    tasks = await self.task_manager.get_user_tasks(user_id)
    
    if not tasks:
        yield event.plain_result("您没有正在运行的任务")
        return
    
    task_list = "\n".join([
        f"🔄 {task.name} (ID: {task.task_id})\n"
        f"   创建时间: {task.created_at.strftime('%H:%M:%S')}"
        for task in tasks
    ])
    
    yield event.plain_result(f"您的任务列表:\n{task_list}")
```

## 插件间通信模式
```python
# 插件事件系统
class PluginEventBus:
    def __init__(self):
        self.listeners: Dict[str, List[callable]] = {}
    
    def emit(self, event_name: str, data: Any):
        """发出事件"""
        if event_name in self.listeners:
            for callback in self.listeners[event_name]:
                try:
                    asyncio.create_task(callback(data))
                except Exception as e:
                    logger.error(f"事件处理失败: {e}")
    
    def on(self, event_name: str, callback: callable):
        """注册事件监听"""
        if event_name not in self.listeners:
            self.listeners[event_name] = []
        self.listeners[event_name].append(callback)

# 全局事件总线
event_bus = PluginEventBus()

# 在插件中使用
class ProducerPlugin(BasePlugin):
    """事件生产者插件"""
    
    @filter.command("trigger_event")
    async def trigger_event(self, event: AstrMessageEvent, message: str):
        """触发事件"""
        event_bus.emit("user_action", {
            "user_id": event.get_sender_id(),
            "message": message,
            "timestamp": time.time()
        })
        yield event.plain_result("事件已触发")

class ConsumerPlugin(BasePlugin):
    """事件消费者插件"""
    
    def __init__(self, context: Context):
        super().__init__(context)
        # 注册事件监听
        event_bus.on("user_action", self.handle_user_action)
    
    async def handle_user_action(self, data: dict):
        """处理用户行为事件"""
        logger.info(f"收到用户事件: {data}")
        # 可以在这里发送通知或记录日志
```

## 国际化支持模式
```python
import json
from typing import Dict

class I18n:
    """国际化支持"""
    def __init__(self, default_lang: str = "zh"):
        self.default_lang = default_lang
        self.translations: Dict[str, Dict[str, str]] = {}
        self.load_translations()
    
    def load_translations(self):
        """加载翻译文件"""
        try:
            # 加载中文
            with open("data/i18n/zh.json", "r", encoding="utf-8") as f:
                self.translations["zh"] = json.load(f)
            
            # 加载英文
            with open("data/i18n/en.json", "r", encoding="utf-8") as f:
                self.translations["en"] = json.load(f)
                
        except FileNotFoundError:
            # 创建默认翻译
            self.translations = {
                "zh": {
                    "hello": "你好",
                    "error": "错误",
                    "success": "成功"
                },
                "en": {
                    "hello": "Hello",
                    "error": "Error",
                    "success": "Success"
                }
            }
    
    def t(self, key: str, lang: str = None, **kwargs) -> str:
        """翻译文本"""
        lang = lang or self.default_lang
        
        if lang in self.translations and key in self.translations[lang]:
            text = self.translations[lang][key]
        elif key in self.translations[self.default_lang]:
            text = self.translations[self.default_lang][key]
        else:
            text = key
        
        # 支持参数替换
        return text.format(**kwargs) if kwargs else text

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.i18n = I18n()

@filter.command("hello")
async def hello(self, event: AstrMessageEvent, lang: str = "zh"):
    """多语言问候"""
    greeting = self.i18n.t("hello", lang)
    yield event.plain_result(greeting)
```
