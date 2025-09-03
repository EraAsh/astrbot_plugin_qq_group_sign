import aiohttp
from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

@register("astrbot_plugin_multi_music", "EraAsh", "QQ音乐和网易云音乐点歌插件", "1.0.0", "https://github.com/AstrBotDevs/astrbot_plugin_music")
class MusicPlugin(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.session = aiohttp.ClientSession()
        self.current_platform = "qq"  # 默认平台为QQ音乐
        self.search_results = {}  # 存储搜索结果
        
        # 读取配置项
        config = self.context.get_config()
        default_api = config.get("default_api", "qqmusic")
        if default_api == "netease":
            self.current_platform = "163"
        elif default_api == "qqmusic":
            self.current_platform = "qq"
        else:
            self.current_platform = "qq"  # 默认使用QQ音乐

    def set_platform(self, platform: str):
        """设置音乐平台"""
        valid_platforms = ["qq", "163"]
        if platform in valid_platforms:
            self.current_platform = platform
            return True
        return False
    
    def get_platform_name(self):
        """获取当前平台的可读名称"""
        platforms = {
            "qq": "QQ音乐",
            "163": "网易云音乐"
        }
        return platforms.get(self.current_platform, "未知平台")
    
    async def search_qq_music(self, keyword: str):
        """搜索QQ音乐"""
        # 使用新的API接口url = f"https://ws.stream.qqmusic.qq.com/{mid}.m4a?fromtag=0&guid=126548448"url = f"http://music.163.com/song/media/outer/url?id={song_id}.mp3"
        url = f"https://api.vkeys.cn/v2/music/tencent?word={keyword}&num=10"
        async with self.session.get(url) as response:
            try:
                data = await response.json()
                if data.get("code") != 200:
                    logger.error(f"QQ音乐搜索失败: {data.get('message', '未知错误')}")
                    return []
                    
                songs = data.get("data", [])
                results = []
                for song in songs:
                    # 处理可能的多版本音乐
                    if "grp" in song and song["grp"]:
                        # 如果有多个版本，使用第一个
                        song_info = song["grp"][0]
                    else:
                        song_info = song
                        
                    results.append({
                        "name": song_info["song"],
                        "artist": song_info["singer"],
                        "id": song_info["id"],
                        "mid": song_info.get("mid", "")
                    })
                return results
            except Exception as e:
                logger.error(f"QQ音乐搜索解析失败: {e}")
                return []

    async def get_qq_music_url(self, mid: str):
        """获取QQ音乐播放链接"""
        if not mid:
            return None
            
        # 使用已验证的API获取QQ音乐播放链接
        # 方法1: 使用官方直链API
        url = f"https://ws.stream.qqmusic.qq.com/{mid}.m4a?fromtag=0&guid=126548448"
        return url

    async def search_163_music(self, keyword: str):
        """搜索网易云音乐"""
        # 使用新的API接口
        url = f"https://api.vkeys.cn/v2/music/netease?word={keyword}&num=10"
        async with self.session.get(url) as response:
            try:
                data = await response.json()
                if data.get("code") != 200:
                    logger.error(f"网易云音乐搜索失败: {data.get('message', '未知错误')}")
                    return []
                
                songs = data.get("data", [])
                # 如果返回的是单个歌曲对象而不是列表，转换为列表
                if isinstance(songs, dict):
                    songs = [songs]
                    
                results = []
                for song in songs:
                    results.append({
                        "name": song["song"],
                        "artist": song["singer"],
                        "id": song["id"]
                    })
                return results
            except Exception as e:
                logger.error(f"网易云音乐搜索解析失败: {e}")
                return []
    
    async def get_163_music_url(self, song_id: str):
        """获取网易云音乐播放链接"""
        if not song_id:
            return None
            
        # 使用已验证的API获取网易云音乐播放链接
        url = f"http://music.163.com/song/media/outer/url?id={song_id}.mp3"
        return url

    async def search_song(self, *args, **kwargs):
        """搜索歌曲的统一接口函数，修复参数数量不匹配问题"""
        # 确保至少有一个参数（event对象）
        if len(args) >= 1:
            event = args[0]
            # 调用已有的dian方法处理搜索请求
            async for result in self.dian(event):
                yield result
        else:
            # 参数不足，无法处理
            yield None

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""
        pass
    
    @filter.command("点歌")
    async def dian(self, event: AstrMessageEvent):
        """多平台音乐点歌"""
        message = event.message_str.strip()
        if not message:
            yield event.plain_result(f"请输入要点的歌曲名，例如：/点歌 七里香\n当前平台：{self.get_platform_name()}\n切换平台请使用：/音乐平台 qq|163")
            return
        
        try:
            # 根据当前平台搜索音乐
            if self.current_platform == "qq":
                songs = await self.search_qq_music(message)
            elif self.current_platform == "163":
                songs = await self.search_163_music(message)
            else:
                songs = await self.search_qq_music(message)  # 默认使用QQ音乐
            
            if not songs:
                yield event.plain_result(f"没有在{self.get_platform_name()}找到与“{message}”相关的歌曲")
                return
            
            # 保存搜索结果
            user_id = event.get_sender_id()
            self.search_results[user_id] = songs
            
            result = f"在{self.get_platform_name()}找到以下歌曲：\n"
            for i, song in enumerate(songs):
                result += f"{i + 1}. {song['name']} - {song['artist']}\n"
            
            result += f"\n回复序号(1-{len(songs)})来获取歌曲链接"
            yield event.plain_result(result)
                
        except Exception as e:
            logger.error(f"点歌失败: {e}")
            yield event.plain_result("点歌失败，请稍后再试")
    
    @filter.command("音乐平台")
    async def set_music_platform(self, event: AstrMessageEvent):
        """设置音乐平台"""
        platform = event.message_str.strip()
        platform_names = {
            "qq": "QQ音乐",
            "163": "网易云音乐"
        }
        
        if not platform:
            current = self.get_platform_name()
            available = "、".join(platform_names.values())
            yield event.plain_result(f"当前平台：{current}\n支持的平台：{available}\n切换平台命令：/音乐平台 [平台名]\n例如：/音乐平台 163")
            return
            
        if self.set_platform(platform):
            yield event.plain_result(f"已切换到{platform_names[platform]}")
        else:
            available = "、".join(platform_names.keys())
            yield event.plain_result(f"不支持的平台：{platform}\n支持的平台有：{available}")

    async def handle_message(self, event: AstrMessageEvent):
        """处理普通消息，用于选择歌曲"""
        message = event.message_str.strip()
        user_id = event.get_sender_id()
        
        # 如果用户有搜索结果且发送的是数字，则认为是在选择歌曲
        if user_id in self.search_results and message.isdigit():
            try:
                index = int(message)
                songs = self.search_results[user_id]
                
                if index < 1 or index > len(songs):
                    return  # 不在有效范围内，不处理
                    
                song = songs[index-1]
                platform = self.get_platform_name()
                
                # 移除已选择的搜索结果
                del self.search_results[user_id]
                
                # 获取播放链接
                play_url = None
                if self.current_platform == "qq":
                    play_url = await self.get_qq_music_url(song.get('mid', song.get('id')))
                elif self.current_platform == "163":
                    play_url = await self.get_163_music_url(song.get('id'))
                
                if play_url:
                    # 创建符合平台样式的卡片
                    card_result = f"[[{song['name']} - {song['artist']}]]({play_url})\n"
                    card_result += f"![专辑封面]({self.get_album_art(song)})\n"
                    
                    # 根据平台添加不同的标识
                    if self.current_platform == "qq":
                        card_result += f"🎵 QQ音乐\n"
                    else:
                        card_result += f"🎵 网易云音乐\n"
                        
                    card_result += f"歌手: {song['artist']}\n"
                    card_result += f"歌曲: {song['name']}"
                    
                    yield event.card_result(card_result)
                else:
                    result = f"正在播放 {platform} 的歌曲：\n"
                    result += f"{song['name']} - {song['artist']}\n"
                    result += "播放链接获取失败\n"
                    yield event.plain_result(result)
                
            except Exception as e:
                logger.error(f"选择歌曲失败: {e}")
                yield event.plain_result("选择歌曲失败，请稍后再试")
        else:
            # 不是数字或者没有搜索结果，不处理
            pass

    def get_album_art(self, song):
        """获取专辑封面，这里使用默认封面作为示例"""
        # 实际应用中可以调用API获取专辑封面
        # 这里返回一个占位符
        return "https://via.placeholder.com/150"

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""
        if self.session:
            await self.session.close()