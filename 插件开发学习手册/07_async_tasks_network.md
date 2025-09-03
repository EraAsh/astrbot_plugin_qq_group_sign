# 异步任务和网络请求快速参考

## 注册异步任务
```python
import asyncio

@register("task_plugin", "author", "异步任务插件", "1.0.0")
class TaskPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.running_tasks = set()
        
        # 启动后台任务
        asyncio.create_task(self.background_task())
        asyncio.create_task(self.periodic_task())

    async def background_task(self):
        """后台任务示例"""
        while True:
            try:
                await asyncio.sleep(300)  # 每5分钟执行一次
                logger.info("后台任务执行")
                
                # 执行定期任务
                await self.do_periodic_work()
                
            except Exception as e:
                logger.error(f"后台任务出错: {e}")
                await asyncio.sleep(60)  # 出错后等待1分钟再试

    async def periodic_task(self):
        """定时提醒任务"""
        while True:
            try:
                await asyncio.sleep(60)  # 每分钟检查
                
                from datetime import datetime
                now = datetime.now()
                
                # 每天9点发送提醒
                if now.hour == 9 and now.minute == 0:
                    await self.send_daily_reminder()
                    
            except Exception as e:
                logger.error(f"定时任务出错: {e}")

    async def send_daily_reminder(self):
        """发送每日提醒"""
        # 这里需要你维护的用户列表
        reminder_users = self.get_reminder_users()
        
        for user_id in reminder_users:
            try:
                from astrbot.api.event import MessageChain
                message = MessageChain().message("早上好！新的一天开始了！")
                await self.context.send_message(user_id, message)
            except Exception as e:
                logger.error(f"发送提醒失败 {user_id}: {e}")

    async def terminate(self):
        """插件停止时清理任务"""
        for task in self.running_tasks:
            task.cancel()
        
        if self.running_tasks:
            await asyncio.gather(*self.running_tasks, return_exceptions=True)
```

## 倒计时任务
```python
@filter.command("countdown")
async def countdown(self, event: AstrMessageEvent, seconds: int):
    """倒计时功能"""
    if seconds <= 0 or seconds > 3600:
        yield event.plain_result("倒计时必须在1-3600秒之间")
        return
    
    yield event.plain_result(f"倒计时{seconds}秒开始！")
    
    # 创建倒计时任务
    task = asyncio.create_task(self.countdown_task(event, seconds))
    self.running_tasks.add(task)
    task.add_done_callback(self.running_tasks.discard)

async def countdown_task(self, event: AstrMessageEvent, seconds: int):
    """倒计时任务实现"""
    try:
        await asyncio.sleep(seconds)
        
        from astrbot.api.event import MessageChain
        message = MessageChain().message(f"⏰ {seconds}秒倒计时结束！")
        await self.context.send_message(event.unified_msg_origin, message)
        
    except asyncio.CancelledError:
        logger.info("倒计时被取消")
    except Exception as e:
        logger.error(f"倒计时任务出错: {e}")
```

## 使用aiohttp进行网络请求
```python
import aiohttp
import json

@filter.command("fetch")
async def fetch_data(self, event: AstrMessageEvent, url: str):
    """获取网络数据"""
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status == 200:
                    content_type = response.headers.get('content-type', '')
                    
                    if 'application/json' in content_type:
                        data = await response.json()
                        yield event.plain_result(f"JSON数据: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                    else:
                        text = await response.text()
                        yield event.plain_result(f"响应: {text[:500]}")
                else:
                    yield event.plain_result(f"请求失败: HTTP {response.status}")
                    
    except aiohttp.ClientTimeout:
        yield event.plain_result("请求超时")
    except aiohttp.ClientError as e:
        yield event.plain_result(f"网络错误: {str(e)}")
    except Exception as e:
        yield event.plain_result(f"未知错误: {str(e)}")

@filter.command("post")
async def post_data(self, event: AstrMessageEvent, url: str, data: str):
    """发送POST请求"""
    try:
        payload = json.loads(data)
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers={'Content-Type': 'application/json'},
                timeout=10
            ) as response:
                result = await response.text()
                yield event.plain_result(f"POST响应: {result[:500]}")
                
    except json.JSONDecodeError:
        yield event.plain_result("数据格式错误，请提供有效的JSON")
    except Exception as e:
        yield event.plain_result(f"请求失败: {str(e)}")
```

## 使用httpx进行请求
```python
import httpx

@filter.command("httpx_get")
async def httpx_get(self, event: AstrMessageEvent, url: str):
    """使用httpx获取数据"""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url)
            
            if response.status_code == 200:
                yield event.plain_result(f"响应: {response.text[:500]}")
            else:
                yield event.plain_result(f"请求失败: {response.status_code}")
                
    except httpx.TimeoutException:
        yield event.plain_result("请求超时")
    except httpx.RequestError as e:
        yield event.plain_result(f"请求错误: {str(e)}")
```

## 带重试的网络请求
```python
async def request_with_retry(self, url: str, max_retries: int = 3):
    """带重试机制的网络请求"""
    for attempt in range(max_retries):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=10) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        raise aiohttp.ClientResponseError(
                            request_info=response.request_info,
                            history=response.history,
                            status=response.status
                        )
                        
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            if attempt == max_retries - 1:  # 最后一次尝试
                raise e
            
            wait_time = 2 ** attempt  # 指数退避
            logger.warning(f"请求失败，{wait_time}秒后重试: {str(e)}")
            await asyncio.sleep(wait_time)

@filter.command("retry_fetch")
async def retry_fetch(self, event: AstrMessageEvent, url: str):
    """带重试的获取数据"""
    try:
        data = await self.request_with_retry(url)
        yield event.plain_result(f"数据: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
    except Exception as e:
        yield event.plain_result(f"请求失败: {str(e)}")
```

## 并发请求
```python
@filter.command("concurrent_fetch")
async def concurrent_fetch(self, event: AstrMessageEvent):
    """并发请求多个URL"""
    urls = [
        "https://api.github.com/users/octocat",
        "https://api.github.com/users/defunkt",
        "https://api.github.com/users/pjhyett"
    ]
    
    try:
        async with aiohttp.ClientSession() as session:
            tasks = [self.fetch_single(session, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = 0
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"URL {urls[i]} 请求失败: {result}")
                else:
                    success_count += 1
            
            yield event.plain_result(f"并发请求完成，成功: {success_count}/{len(urls)}")
            
    except Exception as e:
        yield event.plain_result(f"并发请求失败: {str(e)}")

async def fetch_single(self, session: aiohttp.ClientSession, url: str):
    """单个请求"""
    async with session.get(url) as response:
        return await response.json()
```

## 文件下载
```python
@filter.command("download")
async def download_file(self, event: AstrMessageEvent, url: str, filename: str):
    """下载文件"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    # 确保保存到data目录
                    import os
                    save_path = os.path.join("data", "downloads", filename)
                    os.makedirs(os.path.dirname(save_path), exist_ok=True)
                    
                    with open(save_path, 'wb') as f:
                        async for chunk in response.content.iter_chunked(8192):
                            f.write(chunk)
                    
                    yield event.plain_result(f"文件已下载: {save_path}")
                else:
                    yield event.plain_result(f"下载失败: HTTP {response.status}")
                    
    except Exception as e:
        yield event.plain_result(f"下载出错: {str(e)}")
```

## 定时任务管理
```python
class TaskManager:
    def __init__(self):
        self.tasks = {}
    
    def add_task(self, name: str, coro, interval: int):
        """添加定时任务"""
        if name in self.tasks:
            self.tasks[name].cancel()
        
        async def task_runner():
            while True:
                try:
                    await coro()
                    await asyncio.sleep(interval)
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error(f"任务 {name} 出错: {e}")
                    await asyncio.sleep(60)
        
        task = asyncio.create_task(task_runner())
        self.tasks[name] = task
        return task
    
    def remove_task(self, name: str):
        """移除定时任务"""
        if name in self.tasks:
            self.tasks[name].cancel()
            del self.tasks[name]
    
    def stop_all(self):
        """停止所有任务"""
        for task in self.tasks.values():
            task.cancel()
        self.tasks.clear()

# 在插件中使用
def __init__(self, context: Context):
    super().__init__(context)
    self.task_manager = TaskManager()
    
    # 添加定时任务
    self.task_manager.add_task("health_check", self.health_check, 300)

async def terminate(self):
    self.task_manager.stop_all()
```

## 错误处理最佳实践
```python
async def safe_network_operation(self, url: str):
    """安全的网络操作"""
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=10)) as session:
            async with session.get(url) as response:
                response.raise_for_status()  # 检查HTTP状态
                return await response.json()
                
    except aiohttp.ClientTimeout:
        logger.error("请求超时")
        raise
    except aiohttp.ClientResponseError as e:
        logger.error(f"HTTP错误: {e.status}")
        raise
    except aiohttp.ClientConnectionError:
        logger.error("连接错误")
        raise
    except json.JSONDecodeError:
        logger.error("JSON解析错误")
        raise
    except Exception as e:
        logger.error(f"未知网络错误: {e}")
        raise
```
