from pathlib import Path
from datetime import datetime, time, timedelta, timezone
import aiohttp
import aiofiles
import json
import asyncio
import os
from typing import List, Optional, Union, Dict, Any
from urllib.parse import urlparse
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools, register
from astrbot.api.message_components import Plain, At
from astrbot.api import logger
from astrbot.api import AstrBotConfig

@register("qq_group_sign", "EraAsh", "QQ群打卡插件，支持自动定时打卡、白名单模式、管理员通知等功能", "2.0.0", "https://github.com/EraAsh/astrbot_plugin_qq_group_sign")
class QQGroupSignPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        self.plugin_data_dir = StarTools.get_data_dir()
        self.plugin_data_dir.mkdir(parents=True, exist_ok=True)
        self.storage_file = self.plugin_data_dir / "group_sign_data.json"
        
        self.task: Optional[asyncio.Task] = None
        self.whitelist_groups: List[str] = []
        self.sign_statistics: Dict[str, Any] = {
            "total_signs": 0,
            "success_count": 0,
            "fail_count": 0,
            "last_sign_time": None
        }
        self.is_active = self.config.get("enable_auto_sign", True)
        self._stop_event = asyncio.Event()
        self.timezone = timezone(timedelta(hours=self.config.get("timezone", 8)))
        self._session: Optional[aiohttp.ClientSession] = None
        self.debug_mode = False
        self.bot_instance = None
        self.platform_name = ""
        
        # 解析打卡时间
        sign_time_str = self.config.get("sign_time", "08:00:00")
        try:
            hour, minute, second = map(int, sign_time_str.split(':'))
            self.sign_time = time(hour, minute, second)
        except:
            self.sign_time = time(8, 0, 0)
            logger.warning(f"打卡时间格式错误，使用默认时间 08:00:00")
        
        asyncio.create_task(self._async_init())
    
    async def _async_init(self):
        await self._load_config()
        logger.info(
            f"QQ群打卡插件初始化完成 | is_active={self.is_active} "
            f"whitelist_mode={self.config.get('whitelist_mode', False)}"
        )
        if self.is_active:
            await self._start_sign_task()

    def _get_next_run_time(self) -> datetime:
        """计算下一次任务执行的本地时间"""
        now = self._get_local_time()
        target_time = now.replace(
            hour=self.sign_time.hour,
            minute=self.sign_time.minute,
            second=self.sign_time.second,
            microsecond=0
        )
        if now >= target_time:
            target_time += timedelta(days=1)
        return target_time

    async def _load_config(self):
        """异步加载配置文件"""
        default_values = {
            "whitelist_groups": [],
            "sign_statistics": {
                "total_signs": 0,
                "success_count": 0,
                "fail_count": 0,
                "last_sign_time": None
            }
        }
        
        try:
            if not await asyncio.to_thread(os.path.exists, self.storage_file):
                logger.debug("配置文件不存在，使用默认值")
                for key, value in default_values.items():
                    setattr(self, key, value)
                return True, "default"
    
            async with aiofiles.open(self.storage_file, 'r', encoding='utf-8') as f:
                try:
                    file_content = await f.read()
                    loaded_data = json.loads(file_content)
                    
                    if not isinstance(loaded_data, dict):
                        raise ValueError("配置文件根节点不是一个JSON对象")
                    
                    # 确保群号统一为字符串类型
                    if "whitelist_groups" in loaded_data:
                        loaded_data["whitelist_groups"] = [str(gid) for gid in loaded_data["whitelist_groups"]]
                    
                    for key in default_values:
                        if key in loaded_data:
                            setattr(self, key, loaded_data[key])
                    
                    return True, "file"
                            
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error(f"配置文件解析失败: {e}")
                    corrupted_file = f"{self.storage_file}.corrupted"
                    await asyncio.to_thread(os.rename, self.storage_file, corrupted_file)
                    logger.warning(f"已备份损坏文件到: {corrupted_file}")
        
        except Exception as e:
            logger.error(f"加载配置异常: {str(e)}", exc_info=True)
        
        # 降级处理：使用默认值
        for key, value in default_values.items():
            if getattr(self, key, None) is None:
                setattr(self, key, value)
        
        logger.warning(f"使用默认配置")
        return False, "default"

    async def _save_config(self) -> bool:
        """原子性异步保存配置"""
        temp_path = f"{self.storage_file}.tmp"
        data = {
            "whitelist_groups": self.whitelist_groups,
            "sign_statistics": self.sign_statistics
        }
        
        try:
            async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
                await f.write(json.dumps(data, ensure_ascii=False, indent=2))
            
            await asyncio.to_thread(os.replace, temp_path, self.storage_file)
            logger.info(f"配置已保存")
            return True
            
        except Exception as e:
            logger.error(f"保存配置失败: {e}")
            try:
                await asyncio.to_thread(os.unlink, temp_path)
            except:
                pass
            return False

    async def _start_sign_task(self):
        """启动打卡任务"""
        if self.is_active and (self.task is None or self.task.done()):
            self._stop_event.clear()
            self.task = asyncio.create_task(self._daily_sign_task())
            logger.info("自动打卡任务已启动")

    def _get_local_time(self) -> datetime:
        return datetime.now(self.timezone)

    async def _perform_group_sign(self, group_id: Union[str, int]) -> dict:
        """执行群打卡"""
        try:
            # 优先使用 NapCat 专用签到 API (如果已捕获 bot 实例)
            if self.bot_instance:
                try:
                    result = await self.bot_instance.api.call_action(
                        'set_group_sign',
                        group_id=int(group_id)
                    )
                    logger.info(f"群 {group_id} 打卡成功，使用 NapCat 专用签到 API")
                    return {"success": True, "message": "打卡成功", "result": result}
                except Exception as api_error:
                    logger.warning(f"NapCat 专用签到 API 调用失败: {api_error}，使用回退方法")

            # 回退方法：发送普通消息
            sign_message = self.config.get("sign_message", "打卡成功！")
            message_chain = [Plain(sign_message)]
            session_str = f"{self.platform_name or 'aiocqhttp'}:group:{group_id}"
            await self.context.send_message(session_str, message_chain)
            
            logger.info(f"群 {group_id} 打卡成功 (回退模式)")
            return {"success": True, "message": "打卡成功"}
            
        except Exception as e:
            error_msg = f"群 {group_id} 打卡失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return {"success": False, "message": error_msg}

    async def _notify_admin(self, message: str):
        """通知管理员"""
        if not self.config.get("admin_notification", True):
            return
            
        try:
            admin_group_id = self.config.get("admin_group_id", "")
            if not admin_group_id:
                logger.info(f"管理员通知 (未配置管理群): {message}")
                return

            notification_msg = f"📊 QQ群打卡通知\n{message}"
            
            # 优先使用平台 API 发送 (如果已捕获 bot 实例)
            if self.bot_instance:
                try:
                    await self.bot_instance.api.call_action(
                        'send_group_msg',
                        group_id=int(admin_group_id),
                        message=notification_msg
                    )
                    logger.info(f"管理员通知已通过 API 发送至群 {admin_group_id}")
                    return
                except Exception as api_error:
                    logger.warning(f"平台 API 通知失败: {api_error}，使用回退方法")

            # 回退方法：使用 context.send_message
            session_str = f"{self.platform_name or 'aiocqhttp'}:group:{admin_group_id}"
            await self.context.send_message(session_str, [Plain(notification_msg)])
            logger.info(f"管理员通知已通过 context.send_message 发送至群 {admin_group_id}")

        except Exception as e:
            logger.error(f"通知管理员失败: {e}")

    async def _sign_target_groups(self, group_list: List[str]) -> str:
        """打卡指定群组列表"""
        if not group_list:
            return "❌ 没有可打卡的群组"
            
        tasks = [self._perform_group_sign(group_id) for group_id in group_list]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # 统计结果
        success_count = 0
        fail_count = 0
        
        # 构建结果消息
        messages = []
        for group_id, result in zip(group_list, results):
            # 处理异常情况
            if isinstance(result, Exception):
                status = f"❌ 失败: {str(result)}"
                fail_count += 1
                logger.error(f"群 {group_id} 打卡异常: {str(result)}", exc_info=True)
            elif isinstance(result, dict):
                if result.get("success", False):
                    status = "✅ 成功"
                    success_count += 1
                else:
                    status = f"❌ 失败: {result.get('message', '未知错误')}"
                    fail_count += 1
            else:
                status = "❌ 失败: 返回结果异常"
                fail_count += 1
            
            messages.append(f"群 {group_id} 打卡{status}")
        
        # 更新统计信息
        self.sign_statistics["total_signs"] += len(group_list)
        self.sign_statistics["success_count"] += success_count
        self.sign_statistics["fail_count"] += fail_count
        self.sign_statistics["last_sign_time"] = datetime.now().isoformat()
        await self._save_config()
        
        summary = f"\n📊 本次打卡统计: 成功 {success_count} 个，失败 {fail_count} 个"
        messages.append(summary)
        
        # 通知管理员
        admin_message = f"完成群组打卡\n成功: {success_count}\n失败: {fail_count}\n总计: {len(group_list)}"
        await self._notify_admin(admin_message)
        
        return "\n".join(messages)

    async def _get_all_groups(self) -> List[str]:
        """获取所有群聊列表"""
        if self.bot_instance:
            try:
                result = await self.bot_instance.api.call_action('get_group_list')
                if isinstance(result, list):
                    group_ids = [str(g['group_id']) for g in result]
                    logger.info(f"通过平台 API 获取到 {len(group_ids)} 个群聊")
                    return group_ids
                else:
                    logger.warning(f"获取群列表返回格式异常: {result}")
            except Exception as e:
                logger.error(f"通过平台 API 获取群列表失败: {e}")
        
        logger.warning("无法自动获取群聊列表。请确保机器人已收到过消息以初始化，或改用白名单模式。")
        return []

    async def _daily_sign_task(self):
        """每日定时打卡任务"""
        while not self._stop_event.is_set():
            try:
                now = self._get_local_time()
                target_time = now.replace(
                    hour=self.sign_time.hour,
                    minute=self.sign_time.minute,
                    second=self.sign_time.second,
                    microsecond=0
                )
                
                if now >= target_time:
                    target_time += timedelta(days=1)
                
                wait_seconds = (target_time - now).total_seconds()
                if wait_seconds > 86400:
                    logger.warning(f"等待时间异常长: {wait_seconds}秒，重置为明天")
                    target_time = now.replace(
                        hour=self.sign_time.hour,
                        minute=self.sign_time.minute,
                        second=self.sign_time.second,
                        microsecond=0
                    ) + timedelta(days=1)
                    wait_seconds = (target_time - now).total_seconds()
                
                logger.info(f"距离下次打卡还有 {wait_seconds:.1f}秒 (将在 {target_time} 执行)")
                
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=wait_seconds)
                    if self._stop_event.is_set():
                        break
                except asyncio.TimeoutError:
                    pass
                
                logger.info("开始执行每日打卡...")
                
                # 确定要打卡的群组
                if self.config.get("whitelist_mode", False):
                    target_groups = self.whitelist_groups
                else:
                    target_groups = await self._get_all_groups()
                    if not target_groups:
                        logger.warning("没有找到任何群聊，请检查配置或使用白名单模式")
                        await self._notify_admin("自动打卡失败：没有找到任何群聊")
                
                if target_groups:
                    result = await self._sign_target_groups(target_groups)
                    logger.info(f"打卡完成: {result}")
                else:
                    logger.warning("没有可打卡的群组")
                    await self._notify_admin("自动打卡失败：没有可打卡的群组")
                
                await asyncio.sleep(1)  # 防止CPU占用过高
                
            except Exception as e:
                logger.error(f"自动打卡任务出错: {e}")
                await asyncio.sleep(60)  # 出错后等待60秒再重试

    @filter.event_message_type(filter.EventMessageType.ALL, priority=999)
    async def _capture_bot_instance(self, event: AstrMessageEvent):
        """捕获机器人实例用于后台任务"""
        if self.bot_instance is None and event.get_platform_name() == "aiocqhttp":
            try:
                from astrbot.core.platform.sources.aiocqhttp.aiocqhttp_message_event import AiocqhttpMessageEvent
                if isinstance(event, AiocqhttpMessageEvent):
                    self.bot_instance = event.bot
                    self.platform_name = "aiocqhttp"
                    logger.info("成功捕获 aiocqhttp 机器人实例，后台 API 调用已启用。")
            except ImportError:
                logger.warning("无法导入 AiocqhttpMessageEvent，后台 API 调用可能受限。")
        # 这是一个后台捕获任务，不需要返回任何消息

    @filter.command("打卡", alias=["群打卡"])
    async def group_sign(self, event: AstrMessageEvent):
        """在当前群聊执行打卡"""
        try:
            # 获取当前群聊ID
            group_id = event.get_group_id()
            if not group_id:
                yield event.chain_result([Plain("❌ 请在群聊中使用此命令")])
                return
            
            yield event.chain_result([Plain(f"🔄 正在为当前群 {group_id} 执行打卡...")])
            
            result = await self._perform_group_sign(group_id)
            
            if result["success"]:
                # 更新统计信息
                self.sign_statistics["total_signs"] += 1
                self.sign_statistics["success_count"] += 1
                self.sign_statistics["last_sign_time"] = datetime.now().isoformat()
                await self._save_config()
                
                yield event.chain_result([Plain(f"✅ 群 {group_id} 打卡成功")])
                
                # 通知管理员
                await self._notify_admin(f"群 {group_id} 手动打卡成功")
            else:
                self.sign_statistics["total_signs"] += 1
                self.sign_statistics["fail_count"] += 1
                await self._save_config()
                
                yield event.chain_result([Plain(f"❌ 群 {group_id} 打卡失败: {result['message']}")])
                await self._notify_admin(f"群 {group_id} 手动打卡失败: {result['message']}")
            
        except Exception as e:
            error_msg = f"❌ 打卡失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield event.chain_result([Plain(error_msg)])

    @filter.command("全群打卡", alias=["打卡所有群"])
    async def sign_all_groups(self, event: AstrMessageEvent):
        """打卡所有群聊"""
        try:
            # 获取所有群聊列表
            target_groups = await self._get_all_groups()
            if not target_groups:
                # 如果无法获取所有群聊，使用白名单群组
                target_groups = self.whitelist_groups
            
            if not target_groups:
                yield event.chain_result([Plain("❌ 没有可打卡的群组，请先配置白名单群组")])
                return
            
            yield event.chain_result([Plain(f"🔄 正在为所有群组执行打卡（共 {len(target_groups)} 个群）...")])
            
            result = await self._sign_target_groups(target_groups)
            yield event.chain_result([Plain(result)])
            
        except Exception as e:
            error_msg = f"❌ 全群打卡失败: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield event.chain_result([Plain(error_msg)])

    @filter.command("打卡菜单")
    async def sign_menu(self, event: AstrMessageEvent):
        """显示打卡插件的所有可用指令"""
        menu_text = """
📋 QQ群打卡插件指令菜单

🎯 基础打卡指令：
• /打卡 - 在当前群聊执行打卡
• /全群打卡 - 对所有群聊执行打卡

⚙️ 自动打卡设置：
• /开启自动打卡 - 启动定时自动打卡
• /关闭自动打卡 - 停止定时自动打卡
• /设置打卡时间 [时间] - 设置打卡时间（格式：HH:MM:SS）
• /打卡状态 - 查看打卡状态和统计信息

📝 白名单管理：
• /添加白名单 [群号] - 添加群号到白名单
• /移除白名单 [群号] - 从白名单移除群号
• /查看白名单 - 查看白名单列表
• /切换模式 - 切换白名单/全群模式

📊 其他功能：
• /打卡菜单 - 显示此帮助菜单

💡 使用提示：
• 白名单模式下只对白名单群组执行打卡
• 全群模式下对所有群聊执行打卡
• 自动打卡时间支持时分秒格式设置
        """
        yield event.chain_result([Plain(menu_text)])

    @filter.command("添加白名单", alias=["加白名单"])
    async def add_whitelist(self, event: AstrMessageEvent, group_id: str):
        """添加群号到白名单"""
        try:
            group_id = group_id.strip()
            if group_id not in self.whitelist_groups:
                self.whitelist_groups.append(group_id)
                await self._save_config()
                yield event.chain_result([Plain(
                    f"✅ 已添加群号 {group_id} 到白名单\n"
                    f"📋 当前白名单: {', '.join(self.whitelist_groups)}"
                )])
            else:
                yield event.chain_result([Plain(f"ℹ️ 群号 {group_id} 已在白名单中")])
        except Exception as e:
            yield event.chain_result([Plain(f"❌ 添加失败: {e}")])

    @filter.command("移除白名单", alias=["删白名单"])
    async def remove_whitelist(self, event: AstrMessageEvent, group_id: str):
        """从白名单中移除群号"""
        try:
            group_id = group_id.strip()
            if group_id in self.whitelist_groups:
                self.whitelist_groups.remove(group_id)
                await self._save_config()
                yield event.chain_result([Plain(
                    f"✅ 已从白名单移除群号 {group_id}\n"
                    f"📋 当前白名单: {', '.join(self.whitelist_groups) if self.whitelist_groups else '无'}"
                )])
            else:
                yield event.chain_result([Plain(f"ℹ️ 群号 {group_id} 不在白名单中")])
        except Exception as e:
            yield event.chain_result([Plain(f"❌ 移除失败: {e}")])

    @filter.command("查看白名单", alias=["白名单列表"])
    async def view_whitelist(self, event: AstrMessageEvent):
        """查看白名单列表"""
        if self.whitelist_groups:
            message = f"📋 当前白名单群组:\n{', '.join(self.whitelist_groups)}"
        else:
            message = "📋 当前白名单为空"
        yield event.chain_result([Plain(message)])

    @filter.command("打卡状态", alias=["打卡统计"])
    async def sign_status(self, event: AstrMessageEvent):
        """查看打卡状态和统计"""
        status = "🟢 自动打卡已开启" if self.is_active else "🔴 自动打卡已停止"
        mode = "📝 白名单模式" if self.config.get("whitelist_mode", False) else "🌐 全群模式"
        
        # 计算下次打卡时间
        target_time = self._get_next_run_time()
        wait_seconds = (target_time - self._get_local_time()).total_seconds()
        
        stats = self.sign_statistics
        stats_msg = f"📊 打卡统计:\n总计: {stats['total_signs']}\n成功: {stats['success_count']}\n失败: {stats['fail_count']}"
        
        if stats['last_sign_time']:
            stats_msg += f"\n上次打卡: {stats['last_sign_time']}"
        
        message = [
            Plain(f"{status}\n"),
            Plain(f"{mode}\n"),
            Plain(f"⏰ 打卡时间: {self.sign_time.strftime('%H:%M:%S')} (UTC+{self.config.get('timezone', 8)})\n"),
            Plain(f"{stats_msg}\n"),
            Plain(f"⏱ 下次打卡: {target_time.strftime('%Y-%m-%d %H:%M:%S')}\n"),
            Plain(f"⏳ 距离下次打卡还有 {wait_seconds:.1f} 秒")
        ]
        yield event.chain_result(message)

    @filter.command("开启自动打卡", alias=["启动打卡"])
    async def start_auto_sign(self, event: AstrMessageEvent):
        """开启自动打卡"""
        self.is_active = True
        self.config["enable_auto_sign"] = True
        self.config.save_config()
        
        await self._start_sign_task()
        
        next_run = self._get_next_run_time()
        yield event.chain_result([Plain(
            f"✅ 自动打卡已开启\n"
            f"⏰ 打卡时间: {self.sign_time.strftime('%H:%M:%S')}\n"
            f"⏱ 下次执行: {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
        )])

    @filter.command("关闭自动打卡", alias=["停止打卡"])
    async def stop_auto_sign(self, event: AstrMessageEvent):
        """关闭自动打卡"""
        if self.is_active:
            self._stop_event.set()
            self.is_active = False
            self.config["enable_auto_sign"] = False
            self.config.save_config()
            
            if self.task:
                self.task.cancel()
                try:
                    await self.task
                except asyncio.CancelledError:
                    logger.info("自动打卡任务已取消")
                except Exception as e:
                    logger.error(f"取消任务时出错: {e}")
                finally:
                    self.task = None
                    
            yield event.chain_result([Plain("🛑 自动打卡已停止")])
        else:
            yield event.chain_result([Plain("ℹ️ 自动打卡未在运行中")])

    @filter.command("设置打卡时间", alias=["打卡时间"])
    async def set_sign_time(self, event: AstrMessageEvent, time_str: str):
        """设置打卡时间"""
        try:
            hour, minute, second = map(int, time_str.split(':'))
            if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
                raise ValueError("时间格式错误")
                
            self.sign_time = time(hour, minute, second)
            self.config["sign_time"] = time_str
            self.config.save_config()
            
            yield event.chain_result([Plain(
                f"✅ 打卡时间已设置为 {time_str}\n"
                f"⏰ 将在每天 {time_str} 执行打卡"
            )])
        except Exception as e:
            yield event.chain_result([Plain(f"❌ 时间格式错误，请使用 HH:MM:SS 格式，例如 08:00:00")])

    @filter.command("切换模式", alias=["打卡模式"])
    async def toggle_mode(self, event: AstrMessageEvent):
        """切换打卡模式（白名单/全群）"""
        current_mode = self.config.get("whitelist_mode", False)
        new_mode = not current_mode
        self.config["whitelist_mode"] = new_mode
        self.config.save_config()
        
        mode_name = "📝 白名单模式" if new_mode else "🌐 全群模式"
        yield event.chain_result([Plain(f"✅ 已切换到 {mode_name}")])

    async def terminate(self):
        """插件终止时执行清理"""
        self._stop_event.set()
        
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        
        if self._session and not self._session.closed:
            await self._session.close()
        
        logger.info("QQ群打卡插件已终止")
