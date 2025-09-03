# LLM集成快速参考

## 基础LLM调用
```python
@filter.command("ask")
async def ask_llm(self, event: AstrMessageEvent, question: str):
    """直接调用LLM"""
    provider = self.context.get_using_provider()
    if not provider:
        yield event.plain_result("LLM未配置")
        return
    
    response = await provider.text_chat(
        prompt=question,
        session_id=None,
        contexts=[],
        image_urls=[],
        func_tool=None,
        system_prompt="你是一个有用的助手"
    )
    
    if response.role == "assistant":
        yield event.plain_result(response.completion_text)
    elif response.role == "tool":
        yield event.plain_result(f"调用工具: {response.tools_call_name}")
```

## 使用AstrBot内部处理机制
```python
@filter.command("chat")
async def chat(self, event: AstrMessageEvent, message: str):
    """使用AstrBot的完整LLM处理流程"""
    yield event.request_llm(
        prompt=message,
        func_tool_manager=self.context.get_llm_tool_manager(),
        session_id=None,
        contexts=[],
        system_prompt="你是一个有用的助手",
        image_urls=[],
        conversation=None
    )
```

## 获取对话上下文
```python
@filter.command("context_chat")
async def context_chat(self, event: AstrMessageEvent, message: str):
    """带上下文的LLM对话"""
    # 获取当前对话
    curr_cid = await self.context.conversation_manager.get_curr_conversation_id(
        event.unified_msg_origin
    )
    conversation = None
    context = []
    
    if curr_cid:
        conversation = await self.context.conversation_manager.get_conversation(
            event.unified_msg_origin, curr_cid
        )
        context = json.loads(conversation.history)
    
    yield event.request_llm(
        prompt=message,
        func_tool_manager=self.context.get_llm_tool_manager(),
        session_id=curr_cid,
        contexts=context,
        conversation=conversation
    )
```

## 注册LLM函数工具
```python
@filter.llm_tool(name="get_weather")
async def get_weather(self, event: AstrMessageEvent, location: str) -> MessageEventResult:
    '''获取天气信息
    
    Args:
        location(string): 地点名称
    '''
    # 模拟获取天气
    weather = f"{location}: 晴天 25°C"
    yield event.plain_result(f"天气: {weather}")

@filter.llm_tool(name="calculate")
async def calculate(self, event: AstrMessageEvent, expression: str) -> MessageEventResult:
    '''计算数学表达式
    
    Args:
        expression(string): 数学表达式
    '''
    try:
        result = eval(expression)  # 生产环境需要安全的计算方法
        yield event.plain_result(f"{expression} = {result}")
    except Exception as e:
        yield event.plain_result(f"计算错误: {str(e)}")
```

## 函数工具注释格式 (重要!)
```python
@filter.llm_tool(name="tool_name")
async def tool_function(self, event: AstrMessageEvent, param1: str, param2: int) -> MessageEventResult:
    '''工具描述
    
    Args:
        param1(string): 参数1描述
        param2(number): 参数2描述
    '''
    # 实现逻辑
    yield event.plain_result("结果")
```

**支持的参数类型**: `string`, `number`, `object`, `array`, `boolean`

## 获取LLM相关对象
```python
# 获取当前使用的提供商
provider = self.context.get_using_provider()

# 获取所有提供商
all_providers = self.context.get_all_providers()

# 获取TTS/STT提供商
tts_provider = self.context.get_using_tts_provider()
stt_provider = self.context.get_using_stt_provider()

# 获取函数工具管理器
func_tools = self.context.get_llm_tool_manager()

# 获取人格列表
personas = self.context.provider_manager.personas
default_persona = self.context.provider_manager.selected_default_persona["name"]
```

## 对话管理
```python
# 获取当前对话ID
curr_cid = await self.context.conversation_manager.get_curr_conversation_id(
    event.unified_msg_origin
)

# 获取对话对象
conversation = await self.context.conversation_manager.get_conversation(
    event.unified_msg_origin, curr_cid
)

# 获取所有对话
conversations = await self.context.conversation_manager.get_conversations(
    event.unified_msg_origin
)

# 新建对话
new_cid = await self.context.conversation_manager.new_conversation(
    event.unified_msg_origin
)

# 解析对话历史
if conversation:
    context = json.loads(conversation.history)
    persona_id = conversation.persona_id
```

## LLM事件钩子
```python
from astrbot.api.provider import ProviderRequest, LLMResponse

@filter.on_llm_request()
async def modify_request(self, event: AstrMessageEvent, req: ProviderRequest):
    """修改LLM请求"""
    req.system_prompt += "\n请用简洁的语言回答。"

@filter.on_llm_response()
async def process_response(self, event: AstrMessageEvent, resp: LLMResponse):
    """处理LLM响应"""
    logger.info(f"LLM响应长度: {len(resp.completion_text)}")
```

## 上下文格式
```python
# OpenAI格式的上下文
contexts = [
    {"role": "system", "content": "你是一个助手"},
    {"role": "user", "content": "你好"},
    {"role": "assistant", "content": "您好!有什么可以帮助您的吗?"},
    {"role": "user", "content": "新问题"}
]
```
