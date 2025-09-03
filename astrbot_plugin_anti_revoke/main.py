import json
import time
from datetime import datetime
from typing import Dict, List, Optional
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger
from astrbot.api.message_components import Plain

@register("astrbot_plugin_anti_revoke", "EraAsh", "QQ防撤回插件，监听QQ群和个人消息撤回事件，自动转发撤回消息给管理员或指定管理群", "v1.0.0", "https://github.com/EraAsh/astrbot_plugin_anti_revoke")
class AntiRevokePlugin(Star):
    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.config = config
        
        # 消息缓存，用于存储最近的消息以便撤回时获取内容
        self.message_cache: Dict[str, Dict] = {}
        self.cache_max_size = 1000  # 最大缓存消息数量
        self.cache_expire_time = 3600  # 缓存过期时间（秒）
        
        # 配置参数
        self.admin_qq_list = self._parse_admin_list(config.get("admin_qq", ""))
        self.admin_group_list = self._parse_admin_list(config.get("admin_group", ""))
        self.enable_group = config.get("enable_group", True)
        self.enable_private = config.get("enable_private", True)
        self.notify_format = config.get("notify_format", "🚫 消息撤回提醒\n\n发送者：{sender_name}({sender_id})\n群聊：{group_name}({group_id})\n时间：{message_time}\n\n撤回内容：\n{message_content}")
        self.enable_ai_filter = config.get("enable_ai_filter", False)
        self.ai_filter_prompt = config.get("ai_filter_prompt", "请判断以下消息是否重要，重要消息包括但不限于：包含重要信息、联系方式、地址、金钱交易、工作安排、学习资料等。如果重要，回复'important'，否则回复'not_important'。只回复这两个词之一。")
        
        logger.info(f"[{self.id}] QQ防撤回插件已加载")
        logger.info(f"[{self.id}] 管理员QQ: {self.admin_qq_list}")
        logger.info(f"[{self.id}] 管理群: {self.admin_group_list}")
        logger.info(f"[{self.id}] 群聊监听: {self.enable_group}, 私聊监听: {self.enable_private}")
        logger.info(f"[{self.id}] AI过滤: {self.enable_ai_filter}")

    def _parse_admin_list(self, admin_str: str) -> List[str]:
        """解析管理员列表"""
        if not admin_str:
            return []
        return [qq.strip() for qq in admin_str.split(",") if qq.strip()]

    def _get_message_key(self, message_id: str, sender_id: str) -> str:
        """生成消息缓存键"""
        return f"{message_id}_{sender_id}"

    def _add_message_to_cache(self, event: AstrMessageEvent):
        """添加消息到缓存"""
        try:
            message_key = self._get_message_key(event.message_obj.message_id, event.get_sender_id())
            
            # 清理过期缓存
            current_time = time.time()
            expired_keys = [
                key for key, msg_data in self.message_cache.items()
                if current_time - msg_data["timestamp"] > self.cache_expire_time
            ]
            for key in expired_keys:
                del self.message_cache[key]
            
            # 如果缓存超过最大大小，删除最旧的消息
            if len(self.message_cache) >= self.cache_max_size:
                oldest_key = min(self.message_cache.keys(), 
                               key=lambda k: self.message_cache[k]["timestamp"])
                del self.message_cache[oldest_key]
            
            # 添加新消息到缓存
            self.message_cache[message_key] = {
                "timestamp": current_time,
                "message_content": event.message_str,
                "message_chain": event.message_obj.message,
                "sender_name": event.get_sender_name(),
                "sender_id": event.get_sender_id(),
                "group_id": event.message_obj.group_id,
                "message_time": datetime.fromtimestamp(event.message_obj.timestamp).strftime("%Y-%m-%d %H:%M:%S"),
                "platform": event.get_platform_name()
            }
            
            logger.debug(f"[{self.id}] 缓存消息: {message_key}")
            
        except Exception as e:
            logger.error(f"[{self.id}] 添加消息到缓存失败: {e}")

    def _get_message_from_cache(self, message_id: str, sender_id: str) -> Optional[Dict]:
        """从缓存获取消息"""
        try:
            message_key = self._get_message_key(message_id, sender_id)
            message_data = self.message_cache.get(message_key)
            
            if message_data:
                # 检查是否过期
                if time.time() - message_data["timestamp"] > self.cache_expire_time:
                    del self.message_cache[message_key]
                    return None
                
                # 从缓存中删除已撤回的消息
                del self.message_cache[message_key]
                return message_data
            
            return None
        except Exception as e:
            logger.error(f"[{self.id}] 从缓存获取消息失败: {e}")
            return None

    async def _is_important_message(self, message_content: str) -> bool:
        """使用AI判断消息是否重要"""
        if not self.enable_ai_filter:
            return True
        
        try:
            provider = self.context.get_using_provider()
            if not provider:
                logger.warning(f"[{self.id}] 未找到可用的LLM提供商，跳过AI过滤")
                return True
            
            # 调用LLM判断消息重要性
            llm_response = await provider.text_chat(
                prompt=f"{self.ai_filter_prompt}\n\n消息内容：{message_content}",
                session_id=None,
                contexts=[],
                image_urls=[],
                func_tool=None,
                system_prompt="你是一个消息重要性判断助手，只回复'important'或'not_important'"
            )
            
            if llm_response and llm_response.completion_text:
                result = llm_response.completion_text.strip().lower()
                logger.info(f"[{self.id}] AI判断结果: {result}")
                return result == "important"
            
            return True
            
        except Exception as e:
            logger.error(f"[{self.id}] AI过滤失败: {e}")
            return True  # 如果AI过滤失败，默认认为消息重要

    async def _send_revoke_notification(self, message_data: Dict):
        """发送撤回通知"""
        try:
            # 构建通知消息
            group_name = "私聊" if not message_data["group_id"] else f"群聊({message_data['group_id']})"
            group_id = message_data["group_id"] or "私聊"
            
            notification = self.notify_format.format(
                sender_name=message_data["sender_name"],
                sender_id=message_data["sender_id"],
                group_name=group_name,
                group_id=group_id,
                message_content=message_data["message_content"],
                message_time=message_data["message_time"]
            )
            
            # 发送给管理员QQ
            for admin_qq in self.admin_qq_list:
                try:
                    await self._send_private_message(admin_qq, notification)
                    logger.info(f"[{self.id}] 已发送撤回通知给管理员QQ: {admin_qq}")
                except Exception as e:
                    logger.error(f"[{self.id}] 发送给管理员QQ {admin_qq} 失败: {e}")
            
            # 发送给管理群
            for group_id in self.admin_group_list:
                try:
                    await self._send_group_message(group_id, notification)
                    logger.info(f"[{self.id}] 已发送撤回通知给管理群: {group_id}")
                except Exception as e:
                    logger.error(f"[{self.id}] 发送给管理群 {group_id} 失败: {e}")
                    
        except Exception as e:
            logger.error(f"[{self.id}] 发送撤回通知失败: {e}")

    async def _send_private_message(self, user_id: str, message: str):
        """发送私聊消息"""
        try:
            # 构建消息链
            from astrbot.api.event import MessageChain
            message_chain = MessageChain().message(message)
            
            # 构建统一消息来源
            unified_msg_origin = f"qq_private_{user_id}"
            
            # 发送消息
            await self.context.send_message(unified_msg_origin, message_chain)
            
        except Exception as e:
            logger.error(f"[{self.id}] 发送私聊消息失败: {e}")
            raise

    async def _send_group_message(self, group_id: str, message: str):
        """发送群聊消息"""
        try:
            # 构建消息链
            from astrbot.api.event import MessageChain
            message_chain = MessageChain().message(message)
            
            # 构建统一消息来源
            unified_msg_origin = f"qq_group_{group_id}"
            
            # 发送消息
            await self.context.send_message(unified_msg_origin, message_chain)
            
        except Exception as e:
            logger.error(f"[{self.id}] 发送群聊消息失败: {e}")
            raise

    @filter.event_message_type(filter.EventMessageType.ALL)
    async def on_message(self, event: AstrMessageEvent):
        """监听所有消息，缓存消息内容"""
        try:
            # 只处理QQ平台的消息
            if event.get_platform_name() not in ["aiocqhttp", "qqofficial"]:
                return
            
            # 检查是否启用相应类型的监听
            if event.message_obj.group_id:  # 群聊
                if not self.enable_group:
                    return
            else:  # 私聊
                if not self.enable_private:
                    return
            
            # 缓存消息
            self._add_message_to_cache(event)
            
        except Exception as e:
            logger.error(f"[{self.id}] 处理消息失败: {e}")

    @filter.platform_adapter_type(filter.PlatformAdapterType.AIOCQHTTP)
    async def on_aiocqhttp_event(self, event: AstrMessageEvent):
        """监听aiocqhttp平台的撤回事件"""
        try:
            # 检查是否为撤回事件
            if hasattr(event.message_obj, 'raw_message') and event.message_obj.raw_message:
                raw_msg = event.message_obj.raw_message
                
                # 检查是否为撤回事件（根据不同协议端的格式）
                if isinstance(raw_msg, dict):
                    # 检查是否为撤回事件
                    if raw_msg.get('post_type') == 'notice' and raw_msg.get('notice_type') == 'message_recall':
                        await self._handle_recall_event(raw_msg)
                    # 检查是否为消息删除事件
                    elif raw_msg.get('type') == 'message' and raw_msg.get('sub_type') == 'delete':
                        await self._handle_recall_event(raw_msg)
                    # 检查其他可能的撤回事件格式
                    elif raw_msg.get('notice_type') == 'friend_msg_recall' or raw_msg.get('notice_type') == 'group_msg_recall':
                        await self._handle_recall_event(raw_msg)
                        
        except Exception as e:
            logger.error(f"[{self.id}] 处理撤回事件失败: {e}")

    @filter.platform_adapter_type(filter.PlatformAdapterType.QQOFFICIAL)
    async def on_qqofficial_event(self, event: AstrMessageEvent):
        """监听QQ官方接口的撤回事件"""
        try:
            # 检查是否为撤回事件
            if hasattr(event.message_obj, 'raw_message') and event.message_obj.raw_message:
                raw_msg = event.message_obj.raw_message
                
                # QQ官方接口的撤回事件格式
                if isinstance(raw_msg, dict):
                    # 检查撤回事件
                    if raw_msg.get('notice_type') == 'message_recall':
                        await self._handle_recall_event(raw_msg)
                    # 检查其他可能的撤回格式
                    elif raw_msg.get('type') == 'recall' or raw_msg.get('sub_type') == 'recall':
                        await self._handle_recall_event(raw_msg)
                        
        except Exception as e:
            logger.error(f"[{self.id}] 处理QQ官方撤回事件失败: {e}")

    async def _handle_recall_event(self, raw_msg: dict):
        """处理撤回事件"""
        try:
            # 获取撤回的消息ID和发送者ID - 兼容多种格式
            message_id = str(raw_msg.get('message_id', '') or raw_msg.get('msg_id', '') or raw_msg.get('id', ''))
            user_id = str(raw_msg.get('user_id', '') or raw_msg.get('sender_id', '') or raw_msg.get('qq', ''))
            
            # 如果还是找不到，尝试从其他字段获取
            if not message_id:
                message_id = str(raw_msg.get('data', {}).get('message_id', ''))
            if not user_id:
                user_id = str(raw_msg.get('data', {}).get('user_id', ''))
            
            if not message_id or not user_id:
                logger.warning(f"[{self.id}] 撤回事件缺少必要信息: {raw_msg}")
                return
            
            # 从缓存获取消息内容
            message_data = self._get_message_from_cache(message_id, user_id)
            if not message_data:
                # 尝试使用不同的缓存键查找
                alternative_keys = [
                    f"{message_id}_{user_id}",
                    f"{message_id}",
                    f"msg_{message_id}",
                    f"id_{message_id}"
                ]
                
                for key in alternative_keys:
                    if key in self.message_cache:
                        message_data = self.message_cache[key]
                        del self.message_cache[key]
                        break
                
                if not message_data:
                    logger.warning(f"[{self.id}] 未找到撤回的消息: message_id={message_id}, user_id={user_id}")
                    return
            
            logger.info(f"[{self.id}] 检测到消息撤回: {message_data['sender_name']}({message_data['sender_id']})")
            
            # 使用AI过滤消息重要性
            if await self._is_important_message(message_data["message_content"]):
                await self._send_revoke_notification(message_data)
            else:
                logger.info(f"[{self.id}] 消息被AI判断为不重要，跳过通知")
                
        except Exception as e:
            logger.error(f"[{self.id}] 处理撤回事件失败: {e}")

    @filter.command("antirevoke", alias={"防撤回", "ar"})
    async def antirevoke_command(self, event: AstrMessageEvent):
        """防撤回插件控制命令"""
        try:
            # 检查权限
            if not event.get_sender_id() in self.admin_qq_list:
                yield event.plain_result("❌ 只有管理员才能使用此命令")
                return
            
            help_text = f"""
🚫 QQ防撤回插件 v1.0.0

📊 当前状态：
• 管理员QQ: {', '.join(self.admin_qq_list) if self.admin_qq_list else '未设置'}
• 管理群: {', '.join(self.admin_group_list) if self.admin_group_list else '未设置'}
• 群聊监听: {'✅' if self.enable_group else '❌'}
• 私聊监听: {'✅' if self.enable_private else '❌'}
• AI过滤: {'✅' if self.enable_ai_filter else '❌'}
• 缓存消息数: {len(self.message_cache)}

💡 使用说明：
请在Web管理面板中配置插件参数，包括管理员QQ、管理群等设置。
            """
            
            yield event.plain_result(help_text)
            
        except Exception as e:
            logger.error(f"[{self.id}] 执行命令失败: {e}")
            yield event.plain_result(f"❌ 执行命令失败: {str(e)}")

    async def terminate(self):
        """插件卸载时的清理工作"""
        try:
            # 清理消息缓存
            self.message_cache.clear()
            logger.info(f"[{self.id}] 插件已卸载，缓存已清理")
        except Exception as e:
            logger.error(f"[{self.id}] 插件卸载时出错: {e}")
