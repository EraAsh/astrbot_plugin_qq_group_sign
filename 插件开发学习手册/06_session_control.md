# 会话控制快速参考

## 基础会话控制
```python
from astrbot.core.utils.session_waiter import session_waiter, SessionController
import astrbot.api.message_components as Comp

@filter.command("game")
async def start_game(self, event: AstrMessageEvent):
    """开始会话控制的游戏"""
    try:
        yield event.plain_result("游戏开始！输入数字猜1-100")
        
        import random
        target = random.randint(1, 100)
        attempts = 0
        
        @session_waiter(timeout=60, record_history_chains=False)
        async def game_waiter(controller: SessionController, event: AstrMessageEvent):
            nonlocal attempts, target
            attempts += 1
            
            try:
                guess = int(event.message_str)
            except ValueError:
                await event.send(event.plain_result("请输入数字！"))
                return
            
            if guess == target:
                await event.send(event.plain_result(f"恭喜！{attempts}次猜中了！"))
                controller.stop()
                return
            elif guess < target:
                await event.send(event.plain_result("太小了"))
            else:
                await event.send(event.plain_result("太大了"))
            
            # 继续会话
            controller.keep(timeout=60, reset_timeout=True)
        
        await game_waiter(event)
        
    except TimeoutError:
        yield event.plain_result("超时！游戏结束")
    except Exception as e:
        yield event.plain_result(f"游戏出错: {str(e)}")
    finally:
        event.stop_event()
```

## SessionController 方法
```python
# 保持会话
controller.keep(timeout=60, reset_timeout=True)
# timeout: 超时时间（秒）
# reset_timeout: True=重置计时器, False=延长当前计时器

# 结束会话
controller.stop()

# 获取历史消息链（需要 record_history_chains=True）
history = controller.get_history_chains()
```

## 会话参数说明
```python
@session_waiter(
    timeout=60,              # 超时时间（秒）
    record_history_chains=False  # 是否记录历史消息链
)
async def waiter_function(controller: SessionController, event: AstrMessageEvent):
    pass
```

## 复杂会话示例
```python
@filter.command("survey")
async def survey(self, event: AstrMessageEvent):
    """问卷调查示例"""
    try:
        yield event.plain_result("开始问卷调查！")
        
        questions = [
            "您的姓名是？",
            "您的年龄是？",
            "您喜欢的颜色是？"
        ]
        answers = []
        current_q = 0
        
        @session_waiter(timeout=120, record_history_chains=True)
        async def survey_waiter(controller: SessionController, event: AstrMessageEvent):
            nonlocal current_q, answers
            
            if event.message_str.strip() == "退出":
                await event.send(event.plain_result("问卷已取消"))
                controller.stop()
                return
            
            # 记录答案
            answers.append(event.message_str)
            current_q += 1
            
            if current_q < len(questions):
                # 继续下一题
                await event.send(event.plain_result(f"问题{current_q + 1}: {questions[current_q]}"))
                controller.keep(timeout=120, reset_timeout=True)
            else:
                # 问卷完成
                result = "问卷完成！您的答案：\n"
                for i, (q, a) in enumerate(zip(questions, answers)):
                    result += f"{i+1}. {q} {a}\n"
                
                await event.send(event.plain_result(result))
                controller.stop()
        
        # 开始第一题
        yield event.plain_result(f"问题1: {questions[0]}")
        await survey_waiter(event)
        
    except TimeoutError:
        yield event.plain_result("问卷超时")
    finally:
        event.stop_event()
```

## 自定义会话ID算子
```python
from astrbot.core.utils.session_waiter import SessionFilter

class GroupSessionFilter(SessionFilter):
    """以群组为单位的会话过滤器"""
    def filter(self, event: AstrMessageEvent) -> str:
        # 返回群组ID作为会话标识
        return event.get_group_id() if event.get_group_id() else event.unified_msg_origin

class UserSessionFilter(SessionFilter):
    """以用户为单位的会话过滤器（默认行为）"""
    def filter(self, event: AstrMessageEvent) -> str:
        return event.unified_msg_origin

# 使用自定义过滤器
@session_waiter(timeout=60, session_filter=GroupSessionFilter())
async def group_waiter(controller: SessionController, event: AstrMessageEvent):
    # 这个会话以整个群为单位，群内任何人发消息都会进入这个会话
    pass
```

## 会话中发送消息的方法
```python
@session_waiter(timeout=60)
async def waiter(controller: SessionController, event: AstrMessageEvent):
    # 方法1: 使用 event.send()
    await event.send(event.plain_result("文本消息"))
    
    # 方法2: 构建消息结果
    result = event.make_result()
    result.chain = [Comp.Plain("自定义消息")]
    await event.send(result)
    
    # 方法3: 使用消息链
    chain = [
        Comp.At(qq=event.get_sender_id()),
        Comp.Plain(" 您在会话中")
    ]
    result = event.make_result()
    result.chain = chain
    await event.send(result)
```

## 会话状态管理
```python
@filter.command("state_game")
async def state_game(self, event: AstrMessageEvent):
    """有状态的会话示例"""
    try:
        yield event.plain_result("状态游戏开始！输入'开始'继续")
        
        game_state = {
            'phase': 'waiting_start',
            'score': 0,
            'level': 1
        }
        
        @session_waiter(timeout=180)
        async def state_waiter(controller: SessionController, event: AstrMessageEvent):
            nonlocal game_state
            user_input = event.message_str.strip()
            
            if game_state['phase'] == 'waiting_start':
                if user_input == '开始':
                    game_state['phase'] = 'playing'
                    await event.send(event.plain_result(f"第{game_state['level']}关开始！"))
                    controller.keep(timeout=60, reset_timeout=True)
                else:
                    await event.send(event.plain_result("请输入'开始'来开始游戏"))
                    
            elif game_state['phase'] == 'playing':
                # 游戏逻辑
                if user_input == '正确答案':
                    game_state['score'] += 10
                    game_state['level'] += 1
                    
                    if game_state['level'] > 3:
                        await event.send(event.plain_result(f"游戏完成！总分: {game_state['score']}"))
                        controller.stop()
                    else:
                        await event.send(event.plain_result(f"正确！第{game_state['level']}关"))
                        controller.keep(timeout=60, reset_timeout=True)
                else:
                    await event.send(event.plain_result("错误！请重试"))
        
        await state_waiter(event)
        
    except TimeoutError:
        yield event.plain_result("游戏超时结束")
    finally:
        event.stop_event()
```

## 错误处理
```python
@session_waiter(timeout=60)
async def safe_waiter(controller: SessionController, event: AstrMessageEvent):
    try:
        # 会话逻辑
        user_input = event.message_str
        
        # 处理特殊命令
        if user_input == "退出":
            await event.send(event.plain_result("已退出会话"))
            controller.stop()
            return
        
        # 主要逻辑
        result = process_input(user_input)
        await event.send(event.plain_result(result))
        
        controller.keep(timeout=60, reset_timeout=True)
        
    except Exception as e:
        logger.error(f"会话处理出错: {e}")
        await event.send(event.plain_result("处理出错，请重试"))
        # 可以选择继续或结束会话
        controller.keep(timeout=60, reset_timeout=True)
```

## 注意事项
1. **不能在会话中使用 yield**，必须使用 `await event.send()`
2. **必须调用 `controller.keep()` 或 `controller.stop()`**
3. **超时会抛出 `TimeoutError`**
4. **建议在主函数最后调用 `event.stop_event()`**
5. **会话结束后，用户的下一条消息会正常进入指令处理流程**
