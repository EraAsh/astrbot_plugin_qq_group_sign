import aiohttp
import os
import re
import astrbot.api.message_components as Comp
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api import AstrBotConfig


@register("astrbot_plugin_image_generation", "EraAsh", "基于硅基流动API的AI自主绘图插件", "1.0.0", "https://github.com/YourName/astrbot_plugin_image_generation")
class ImageGenerationPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        
        # 从插件配置中读取设置
        self.api_key = config.get("siliconflow", {}).get("api_key", "")
        self.api_url = config.get("siliconflow", {}).get("api_url", "https://api.siliconflow.cn/v1/images/generations")
        self.model = config.get("siliconflow", {}).get("model", "black-forest-labs/FLUX.1-schnell")
        # 环境变量回落
        env_api_key = os.getenv("SILICONFLOW_API_KEY")
        if env_api_key:
            self.api_key = env_api_key
        env_api_url = os.getenv("SILICONFLOW_API_URL")
        if env_api_url:
            self.api_url = env_api_url
        
        # 绘图关键词模式
        self.drawing_patterns = [
            r"(画|绘|生成|创作|设计).*(图|画|作品)",
            r"(图|画).*(一下|一张|一副)",
            r"能.*画.*吗",
            r"帮我.*画",
            r"给我.*画",
            r"根据.*画",
            r"画个.*",
            r"画一下.*",
            r"画一张.*",
        ]
        
        if not self.api_key:
            logger.warning(f"[{self.id}] 硅基流动API密钥未配置，插件功能将无法使用")

    async def initialize(self):
        """插件初始化方法"""
        self.session = aiohttp.ClientSession()
        logger.info(f"[{self.id}] 插件已初始化")

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息并判断是否需要绘图"""
        # 检查API密钥和是否为机器人自己发送的消息
        if not self.api_key or event.is_self:
            return

        message = event.message_str.strip()
        
        # 检查是否包含绘图关键词
        if not self._is_drawing_request(message):
            return

        # 提取绘图描述
        description = self._extract_drawing_description(message)
        
        if not description:
            description = "一幅美丽的艺术作品"
        
        yield event.plain_result(f"检测到绘图请求，正在为您生成：{description}")

        try:
            # 调用硅基流动API生成图片
            image_url = await self._call_siliconflow_api(description)
            if image_url:
                # 构建消息链发送图片
                message_chain = [
                    Comp.Plain("✨ 图片生成完成！\n\n"),
                    Comp.Plain(f"**描述：** {description}\n"),
                    Comp.Plain(f"**模型：** {self.model}\n\n"),
                    Comp.Image.fromURL(image_url)
                ]
                yield event.chain_result(message_chain)
            else:
                yield event.plain_result("图片生成失败，请稍后再试")
                
        except Exception as e:
            logger.error(f"[{self.id}] 图片生成失败: {e}")
            yield event.plain_result(f"图片生成失败: {str(e)}")
    
    def _is_drawing_request(self, message: str) -> bool:
        """判断是否为绘图请求"""
        for pattern in self.drawing_patterns:
            if re.search(pattern, message):
                return True
        return False
    
    def _extract_drawing_description(self, message: str) -> str:
        """提取绘图描述"""
        # 移除关键词，提取核心描述
        description = message
        keywords = ["画", "绘", "生成", "创作", "设计", "帮我", "给我", "画个", "画一张", "画一下"]
        
        for kw in keywords:
            description = description.replace(kw, "").strip()
            
        # 移除标点符号
        description = re.sub(r'[，。！？,\.!\?]', '', description).strip()
        
        return description

    async def _call_siliconflow_api(self, prompt: str):
        """调用硅基流动API生成图片"""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "prompt": prompt,
            "response_format": "url"
        }
        
        max_retries = 3
        retry_delay = 2  # 重试延迟(秒)
        
        for attempt in range(max_retries):
            try:
                async with self.session.post(self.api_url, headers=headers, json=payload) as response:
                    if response.status == 200:
                        data = await response.json()
                        if "data" in data and len(data["data"]) > 0:
                            image_url = data["data"][0]["url"]
                            
                            # 验证图片URL格式
                            if not self._validate_image_url(image_url):
                                logger.warning(f"[{self.id}] 无效的图片URL: {image_url}")
                                continue
                                
                            return image_url
                        else:
                            logger.error(f"[{self.id}] API返回数据格式错误: {data}")
                    elif response.status == 429:  # 频率限制
                        retry_after = int(response.headers.get('Retry-After', retry_delay))
                        logger.warning(f"[{self.id}] 频率限制，等待 {retry_after} 秒后重试...")
                        await asyncio.sleep(retry_after)
                        continue
                    else:
                        error_text = await response.text()
                        logger.error(f"[{self.id}] API调用失败: {response.status} - {error_text}")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                logger.error(f"[{self.id}] 网络请求异常: {e}")
            
            # 如果不是最后一次尝试，等待后重试
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay * (attempt + 1))
        
        return None

    def _validate_image_url(self, url: str) -> bool:
        """验证图片URL格式"""
        # 检查URL是否以有效图片扩展名结尾
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(url.lower().endswith(ext) for ext in valid_extensions)

    async def terminate(self):
        """插件销毁方法"""
        if hasattr(self, 'session') and self.session:
            await self.session.close()
        logger.info(f"[{self.id}] 插件已终止")
