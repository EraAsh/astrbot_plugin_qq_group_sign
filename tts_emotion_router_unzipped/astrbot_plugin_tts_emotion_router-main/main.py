# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import logging
import random
import re
import time
import hashlib
from dataclasses import dataclass
import sys
from pathlib import Path
import importlib
from typing import Dict, List, Optional
import asyncio

def _ensure_compatible_astrbot():
    """确保 astrbot API 兼容；若宿主astrbot不满足需要，回退到插件自带的 AstrBot。"""
    _PLUGIN_DIR = Path(__file__).parent
    _VENDORED_ROOT = _PLUGIN_DIR / "AstrBot"
    _VENDORED_ASTROBOT = _VENDORED_ROOT / "astrbot"
    root_str = str(_PLUGIN_DIR.resolve())

    def _import_host_first():
        if _VENDORED_ASTROBOT.exists() and "astrbot" not in sys.modules:
            _orig = list(sys.path)
            try:
                # 临时移除插件路径，优先导入宿主 AstrBot
                sys.path = [p for p in sys.path if not (isinstance(p, str) and p.startswith(root_str))]
                importlib.import_module("astrbot")
            finally:
                sys.path = _orig

    def _is_compatible() -> bool:
        try:
            import importlib as _il
            _il.import_module("astrbot.api.event.filter")
            _il.import_module("astrbot.core.platform")
            return True
        except Exception:
            return False

    def _force_vendored():
        try:
            sys.modules.pop("astrbot", None)
            importlib.invalidate_caches()
            # 确保优先搜索插件自带 AstrBot
             # 确保优先搜索插件自带 AstrBot
            if str(_VENDORED_ROOT) not in sys.path:
                sys.path.insert(0, str(_VENDORED_ROOT))
            importlib.import_module("astrbot")
            logging.info("TTSEmotionRouter: forced to vendored AstrBot: %s", (_VENDORED_ASTROBOT / "__init__.py").as_posix())
        except Exception:
            pass

    # 1) 优先尝试宿主
    try:
        _import_host_first()
    except Exception:
        pass
    # 2) 若不兼容，则强制改用内置 AstrBot
    if not _is_compatible() and _VENDORED_ASTROBOT.exists():
        _force_vendored()

try:
    _ensure_compatible_astrbot()
except Exception:
    pass

# 兼容不同 AstrBot 版本的导入：event 可能是模块(event.py)也可能是包(event/)
try:
    # 优先常规路径
    from astrbot.api.event import AstrMessageEvent  # type: ignore
except Exception:  # pragma: no cover - 旧版本回退
    from astrbot.core.platform import AstrMessageEvent  # type: ignore

# 统一获取 filter 装饰器集合：
try:
    # 新版通常支持 from astrbot.api.event import filter
    from astrbot.api.event import filter as filter  # type: ignore
except Exception:
    try:
        # 另一些版本可 import 子模块
        import importlib as _importlib
        filter = _importlib.import_module("astrbot.api.event.filter")  # type: ignore
    except Exception:
        # 最后回退：用 register 构造一个拥有同名方法的轻量代理
        try:
            import astrbot.core.star.register as _reg  # type: ignore

            class _FilterCompat:
                def command(self, *a, **k):
                    return _reg.register_command(*a, **k)

                def on_llm_request(self, *a, **k):
                    return _reg.register_on_llm_request(*a, **k)

                def on_llm_response(self, *a, **k):
                    return _reg.register_on_llm_response(*a, **k)

                def on_decorating_result(self, *a, **k):
                    return _reg.register_on_decorating_result(*a, **k)

                def after_message_sent(self, *a, **k):
                    return _reg.register_after_message_sent(*a, **k)

                # 兼容某些版本名为 on_after_message_sent
                def on_after_message_sent(self, *a, **k):
                    return _reg.register_after_message_sent(*a, **k)

            filter = _FilterCompat()  # type: ignore
        except Exception as _e:  # 若三种方式均失败，抛出原错误
            raise _e
from astrbot.api.star import Context, Star, register
# 优先使用 core 版本的组件类型以匹配 RespondStage 校验逻辑，失败时回退到 api 版本
try:  # pragma: no cover - 运行期按宿主 AstrBot 能力选择
    from astrbot.core.message.components import Record, Plain  # type: ignore
except Exception:  # pragma: no cover - 旧版本回退
    from astrbot.api.message_components import Record, Plain  # type: ignore
from astrbot.core.config.astrbot_config import AstrBotConfig
from astrbot.api.provider import LLMResponse
from astrbot.core.message.message_event_result import ResultContentType

from .emotion.infer import EMOTIONS
from .emotion.classifier import HeuristicClassifier  # LLMClassifier 不再使用
from .tts.provider_siliconflow import SiliconFlowTTS
from .utils.audio import ensure_dir, cleanup_dir

# 记录 astrbot 实际来源，便于远端排查“导入到插件内自带 AstrBot”的问题
try:
    import astrbot as _ab_mod  # type: ignore
    logging.info("TTSEmotionRouter: using astrbot from %s", getattr(_ab_mod, "__file__", None))
except Exception:
    pass

CONFIG_FILE = Path(__file__).parent / "config.json"  # 旧版本地文件，作为迁移来源
TEMP_DIR = Path(__file__).parent / "temp"


@dataclass
class SessionState:
    last_ts: float = 0.0
    pending_emotion: Optional[str] = None  # 基于隐藏标记的待用情绪
    last_tts_content: Optional[str] = None  # 最后生成的TTS内容（防重复）
    last_tts_time: float = 0.0  # 最后TTS生成时间
    last_assistant_text: Optional[str] = None  # 最近一次助手可读文本（用于兜底入库）
    last_assistant_text_time: float = 0.0


@register(
    "astrbot_plugin_tts_emotion_router",
    "木有知",
    "按情绪路由到不同音色的TTS插件",
    "0.2.2",
)
class TTSEmotionRouter(Star):
    def __init__(self, context: Context, config: Optional[dict] = None):
        super().__init__(context)
        # 1) 首选面板生成的插件配置（data/config/tts_emotion_router_config.json）
        #    当 _conf_schema.json 存在时，StarManager 会传入 AstrBotConfig
        if isinstance(config, AstrBotConfig):
            self.config = config
            # 若是首次创建且旧版本地 config.json 存在，则迁移一次
            try:
                if getattr(self.config, "first_deploy", False) and CONFIG_FILE.exists():
                    disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                    # 仅拷贝已知字段，避免脏键
                    for k in [
                        "global_enable",
                        "enabled_sessions",
                        "disabled_sessions",
                        "prob",
                        "text_limit",
                        "cooldown",
                        "allow_mixed",
                        "api",
                        "voice_map",
                        "emotion",
                        "speed_map",
                    ]:
                        if k in disk:
                            self.config[k] = disk[k]
                    self.config.save_config()
            except Exception:
                pass
        else:
            # 兼容旧版：直接读写插件目录下的 config.json
            self.config = self._load_config(config or {})

        api = self.config.get("api", {})
        api_url = api.get("url", "")
        api_key = api.get("key", "")
        api_model = api.get("model", "gpt-tts-pro")
        api_format = api.get("format", "mp3")  # 默认 mp3，减少部分平台播放噪点
        api_speed = float(api.get("speed", 1.0))
        api_gain = float(api.get("gain", 5.0))  # +50% 增益
        api_sr = int(
            api.get("sample_rate", 44100 if api_format in ("mp3", "wav") else 48000)
        )
        # 初始化 TTS 客户端（支持 gain 与 sample_rate）
        self.tts = SiliconFlowTTS(
            api_url,
            api_key,
            api_model,
            api_format,
            api_speed,
            gain=api_gain,
            sample_rate=api_sr,
        )

        self.voice_map: Dict[str, str] = self.config.get("voice_map", {})
        self.speed_map: Dict[str, float] = self.config.get("speed_map", {}) or {}
        self.global_enable: bool = bool(self.config.get("global_enable", True))
        self.enabled_sessions: List[str] = list(self.config.get("enabled_sessions", []))
        self.disabled_sessions: List[str] = list(
            self.config.get("disabled_sessions", [])
        )
        self.prob: float = float(self.config.get("prob", 0.35))
        self.text_limit: int = int(self.config.get("text_limit", 80))
        self.cooldown: int = int(self.config.get("cooldown", 20))
        self.allow_mixed: bool = bool(self.config.get("allow_mixed", False))
        # 智能检测：自动识别并跳过代码内容，避免影响正常文本显示
        self.smart_detection: bool = bool(self.config.get("smart_detection", True))  # 默认启用
        # 情绪分类：仅启发式 + 隐藏标记
        emo_cfg = self.config.get("emotion", {}) or {}
        self.heuristic_cls = HeuristicClassifier()
        # 标记驱动配置（不与表情包插件冲突：仅识别 [EMO:happy] 这类专属标记）
        marker_cfg = (emo_cfg.get("marker") or {}) if isinstance(emo_cfg, dict) else {}
        self.emo_marker_enable: bool = bool(marker_cfg.get("enable", True))  # 默认开启
        self.emo_marker_tag: str = str(marker_cfg.get("tag", "EMO"))
        try:
            tag = re.escape(self.emo_marker_tag)
            self._emo_marker_re = re.compile(
                rf"\[\s*{tag}\s*:\s*(happy|sad|angry|neutral)\s*\]", re.I
            )
        except Exception:
            self._emo_marker_re = None
        # 额外：更宽松的去除规则（允许 [EMO] / [EMO:] / 全角【EMO】 以及纯单词 emo 开头等变体）
        try:
            tag = re.escape(self.emo_marker_tag)
            # 允许“:[label]”可缺省label，接受半/全角冒号及连字符，锚定开头以仅清理头部
            self._emo_marker_re_any = re.compile(
                rf"^[\s\ufeff]*[\[\(【]\s*{tag}\s*(?:[:\uff1a-]\s*[a-z]*)?\s*[\]\)】]",
                re.I,
            )
            # 头部 token：支持 [EMO] / [EMO:] / 【EMO：】 / emo / emo:happy / 等，label 可缺省（限定四选一）
            self._emo_head_token_re = re.compile(
                rf"^[\s\ufeff]*(?:[\[\(【]\s*{tag}\s*(?:[:\uff1a-]\s*(?P<lbl>happy|sad|angry|neutral))?\s*[\]\)】]|(?:{tag}|emo)\s*(?:[:\uff1a-]\s*(?P<lbl2>happy|sad|angry|neutral))?)\s*[,，。:\uff1a-]*\s*",
                re.I,
            )
            # 头部 token（英文任意标签）：如 [EMO:confused]，先取 raw 再做同义词归一化
            self._emo_head_anylabel_re = re.compile(
                rf"^[\s\ufeff]*[\[\(【]\s*{tag}\s*[:\uff1a-]\s*(?P<raw>[a-z]+)\s*[\]\)】]",
                re.I,
            )
        except Exception:
            self._emo_marker_re_any = None
            self._emo_head_token_re = None
            self._emo_head_anylabel_re = None

        self._session_state: Dict[str, SessionState] = {}
        # 事件级防重：最近发送签名与进行中签名
        self._recent_sends: Dict[str, float] = {}
        self._inflight_sigs: set[str] = set()
        ensure_dir(TEMP_DIR)
        # 初始清理：删除超过2小时的文件
        cleanup_dir(TEMP_DIR, ttl_seconds=2 * 3600)

        # 简单关键词启发，用于无标记时的中性偏置判定
        try:
            self._emo_kw = {
                "happy": re.compile(
                    r"(开心|快乐|高兴|喜悦|愉快|兴奋|喜欢|令人开心|挺好|不错|开心|happy|joy|delight|excited|great|awesome|lol)",
                    re.I,
                ),
                "sad": re.compile(
                    r"(伤心|难过|沮丧|低落|悲伤|哭|流泪|难受|失望|委屈|心碎|sad|depress|upset|unhappy|blue|tear)",
                    re.I,
                ),
                "angry": re.compile(
                    r"(生气|愤怒|火大|恼火|气愤|气死|怒|怒了|生气了|angry|furious|mad|rage|annoyed|irritat)",
                    re.I,
                ),
            }
        except Exception:
            self._emo_kw = {
                "happy": re.compile(r"happy|joy|delight|excited", re.I),
                "sad": re.compile(r"sad|depress|upset|unhappy", re.I),
                "angry": re.compile(r"angry|furious|mad|rage", re.I),
            }

    def _is_our_record(self, comp) -> bool:
        try:
            if not isinstance(comp, Record):
                return False
            f = getattr(comp, "file", "") or ""
            if not f:
                return False
            fpath = Path(f)
            return str(fpath).startswith(str((Path(__file__).parent / "temp").resolve()))
        except Exception:
            return False

    def _validate_audio_file(self, audio_path: Path) -> bool:
        """验证音频文件是否有效"""
        try:
            if not audio_path.exists():
                logging.error(f"TTSEmotionRouter: 音频文件不存在: {audio_path}")
                return False
            
            file_size = audio_path.stat().st_size
            if file_size == 0:
                logging.error(f"TTSEmotionRouter: 音频文件为空: {audio_path}")
                return False
            
            if file_size < 100:  # 小于100字节通常是无效文件
                logging.error(f"TTSEmotionRouter: 音频文件太小({file_size}字节): {audio_path}")
                return False
            
            # 检查文件扩展名
            if audio_path.suffix.lower() not in ['.mp3', '.wav', '.opus', '.pcm']:
                logging.warning(f"TTSEmotionRouter: 音频文件格式可能不支持: {audio_path}")
            
            logging.info(f"TTSEmotionRouter: 音频文件验证通过: {audio_path} ({file_size}字节)")
            return True
        except Exception as e:
            logging.error(f"TTSEmotionRouter: 音频文件验证失败: {audio_path}, 错误: {e}")
            return False

    def _normalize_audio_path(self, audio_path: Path) -> str:
        """规范化音频文件路径以提高协议端兼容性"""
        try:
            # 1. 确保使用绝对路径
            abs_path = audio_path.resolve()
            
            # 2. Windows路径格式转换
            import os
            normalized = os.path.normpath(str(abs_path))
            
            # 3. 对于某些协议端，可能需要使用正斜杠
            if os.name == 'nt':  # Windows
                # 先尝试使用反斜杠路径（标准Windows格式）
                return normalized
            else:
                # Unix-like系统使用正斜杠
                return normalized.replace('\\', '/')
        except Exception as e:
            logging.error(f"TTSEmotionRouter: 路径规范化失败: {audio_path}, 错误: {e}")
            return str(audio_path)

    def _create_fallback_text_result(self, text: str, event: AstrMessageEvent) -> None:
        """创建文本回退结果"""
        try:
            result = event.get_result()
            if result and hasattr(result, 'chain'):
                # 清空现有链并添加文本结果
                result.chain.clear()
                result.chain.append(Plain(text))
                logging.info(f"TTSEmotionRouter: 已回退到文本消息: {text[:50]}...")
        except Exception as e:
            logging.error(f"TTSEmotionRouter: 创建文本回退失败: {e}")

    def _try_copy_to_accessible_location(self, audio_path: Path) -> Optional[Path]:
        """尝试将音频文件复制到更容易访问的位置"""
        try:
            import tempfile
            import shutil
            
            # 使用系统临时目录
            temp_dir = Path(tempfile.gettempdir()) / "astrbot_audio"
            temp_dir.mkdir(exist_ok=True)
            
            # 生成新的文件名
            import uuid
            new_filename = f"tts_{uuid.uuid4().hex[:8]}{audio_path.suffix}"
            new_path = temp_dir / new_filename
            
            # 复制文件
            shutil.copy2(audio_path, new_path)
            
            if self._validate_audio_file(new_path):
                logging.info(f"TTSEmotionRouter: 音频文件已复制到: {new_path}")
                return new_path
            else:
                # 清理失败的复制
                try:
                    new_path.unlink()
                except:
                    pass
                return None
        except Exception as e:
            logging.error(f"TTSEmotionRouter: 复制音频文件失败: {e}")
            return None

    # ---------------- Config helpers -----------------
    def _load_config(self, cfg: dict) -> dict:
        # 合并磁盘config与传入config，便于热更
        try:
            if CONFIG_FILE.exists():
                disk = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            else:
                disk = {}
        except Exception:
            disk = {}
        merged = {**disk, **(cfg or {})}
        try:
            CONFIG_FILE.write_text(
                json.dumps(merged, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception:
            pass
        return merged

    def _save_config(self):
        # 面板配置优先保存到 data/config/tts_emotion_router_config.json
        if isinstance(self.config, AstrBotConfig):
            self.config.save_config()
        else:
            try:
                CONFIG_FILE.write_text(
                    json.dumps(self.config, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            except Exception:
                pass

    def _sess_id(self, event: AstrMessageEvent) -> str:
        gid = ""
        try:
            gid = event.get_group_id()
        except Exception:
            gid = ""
        if gid:
            return f"group_{gid}"
        return f"user_{event.get_sender_id()}"

    def _is_session_enabled(self, sid: str) -> bool:
        if self.global_enable:
            return sid not in self.disabled_sessions
        return sid in self.enabled_sessions

    def _normalize_text(self, text: str) -> str:
        """移除不可见字符与BOM，过滤代码块和emoji，避免破坏头部匹配。"""
        if not text:
            return text
        invisibles = [
            "\ufeff",  # BOM
            "\u200b",
            "\u200c",
            "\u200d",
            "\u200e",
            "\u200f",  # ZW* & RTL/LTR marks
            "\u202a",
            "\u202b",
            "\u202c",
            "\u202d",
            "\u202e",  # directional marks
        ]
        for ch in invisibles:
            text = text.replace(ch, "")
        
        # 新增：过滤代码块
        text = self._filter_code_blocks(text)
        if not text:  # 如果过滤后为空，直接返回
            return text
        
        # 新增：过滤emoji和QQ表情
        text = self._filter_emoji_and_qq_expressions(text)
        
        return text

    def _normalize_label(self, label: Optional[str]) -> Optional[str]:
        """将任意英文/中文情绪词映射到四选一。
        例：confused->neutral，upset->sad，furious->angry，delighted->happy 等。"""
        if not label:
            return None
        lbl = label.strip().lower()
        mapping = {
            "happy": {
                "happy",
                "joy",
                "joyful",
                "cheerful",
                "delighted",
                "excited",
                "smile",
                "positive",
                "开心",
                "快乐",
                "高兴",
                "喜悦",
                "兴奋",
                "愉快",
            },
            "sad": {
                "sad",
                "sorrow",
                "sorrowful",
                "depressed",
                "down",
                "unhappy",
                "cry",
                "crying",
                "tearful",
                "blue",
                "upset",
                "伤心",
                "难过",
                "沮丧",
                "低落",
                "悲伤",
                "流泪",
            },
            "angry": {
                "angry",
                "mad",
                "furious",
                "annoyed",
                "irritated",
                "rage",
                "rageful",
                "wrath",
                "生气",
                "愤怒",
                "恼火",
                "气愤",
            },
            "neutral": {
                "neutral",
                "calm",
                "plain",
                "normal",
                "objective",
                "ok",
                "fine",
                "meh",
                "average",
                "confused",
                "uncertain",
                "unsure",
                "平静",
                "冷静",
                "一般",
                "中立",
                "客观",
                "困惑",
                "迷茫",
            },
        }
        for k, vs in mapping.items():
            if lbl in vs:
                return k
        return None

    def _pick_voice_for_emotion(self, emotion: str):
        """根据情绪选择音色：优先 exact -> neutral -> 偏好映射 -> 任意非空。
        返回 (voice_key, voice_uri)；若无可用则 (None, None)。"""
        vm = self.voice_map or {}
        # exact
        v = vm.get(emotion)
        if v:
            return emotion, v
        # neutral
        v = vm.get("neutral")
        if v:
            return "neutral", v
        # 偏好映射（让缺失的项落到最接近的可用音色）
        pref = {"sad": "angry", "angry": "angry", "happy": "happy", "neutral": "happy"}
        for key in [pref.get(emotion), "happy", "angry"]:
            if key and vm.get(key):
                return key, vm[key]
        # 兜底：任意非空
        for k, v in vm.items():
            if v:
                return k, v
        return None, None

    def _strip_emo_head(self, text: str) -> tuple[str, Optional[str]]:
        """从文本开头剥离各种 EMO/emo 标记变体，并返回(清理后的文本, 解析到的情绪或None)。"""
        if not text:
            return text, None
        # 优先用宽松的头部匹配（限定四选一）
        if self._emo_head_token_re:
            m = self._emo_head_token_re.match(text)
            if m:
                label = (m.group("lbl") or m.group("lbl2") or "").lower()
                if label not in EMOTIONS:
                    label = None
                cleaned = self._emo_head_token_re.sub("", text, count=1)
                return cleaned.strip(), label
        # 其次：捕获任意英文标签，再做同义词归一化
        if self._emo_head_anylabel_re:
            m2 = self._emo_head_anylabel_re.match(text)
            if m2:
                raw = (m2.group("raw") or "").lower()
                label = self._normalize_label(raw)
                cleaned = self._emo_head_anylabel_re.sub("", text, count=1)
                return cleaned.strip(), label
        # 最后：去掉任何形态头部标记（即便无法识别标签含义也移除）
        if self._emo_marker_re_any and text.lstrip().startswith(("[", "【", "(")):
            cleaned = self._emo_marker_re_any.sub("", text, count=1)
            return cleaned.strip(), None
        return text, None

    def _is_command_input(self, event: AstrMessageEvent) -> bool:
        """检测用户输入是否为命令，用于判断回复是否应跳过TTS"""
        try:
            # 获取用户消息内容
            user_message = getattr(event, 'message_obj', None)
            if not user_message or not hasattr(user_message, 'message_str'):
                return False
            
            msg_content = getattr(user_message, 'message_str', '') or ''
            if not msg_content:
                return False
            
            msg_content = msg_content.strip().lower()
            
            # 1. 插件TTS相关命令
            tts_commands = [
                'tts_status', 'tts_on', 'tts_off', 'tts_global_on', 'tts_global_off',
                'tts_prob', 'tts_limit', 'tts_cooldown', 'tts_test', 'tts_debug',
                'tts_emote', 'tts_marker_on', 'tts_marker_off', 'tts_mixed_on',
                'tts_mixed_off', 'tts_smart_on', 'tts_smart_off', 'tts_gain',
                'tts_test_problematic'
            ]
            
            for cmd in tts_commands:
                if msg_content.startswith(cmd.lower()):
                    return True
            
            # 2. 系统命令（以/或!开头）
            if msg_content.startswith(('/help', '/status', '/config', '/set', '/get', '/version')):
                return True
            if msg_content.startswith(('!help', '!status', '!config', '!set', '!get', '!version')):
                return True
            
            # 3. 常见设置命令模式
            setting_patterns = [
                '设置', '配置', 'config', 'setting', 'set ', 'get ',
                '查看状态', '状态', 'status', '帮助', 'help'
            ]
            
            for pattern in setting_patterns:
                if msg_content.startswith(pattern):
                    return True
            
            # 4. 插件管理命令
            plugin_patterns = [
                '插件', 'plugin', '启用', '禁用', 'enable', 'disable',
                '安装', 'install', '卸载', 'uninstall'
            ]
            
            for pattern in plugin_patterns:
                if msg_content.startswith(pattern):
                    return True
            
            return False
            
        except Exception:
            # 出现异常时保守处理，不认为是命令
            return False

    def _build_emotion_instruction(self) -> str:
        """构建非侵入性的情绪指令"""
        tag = self.emo_marker_tag
        return (
            f"[可选] 如果合适，可在回复开头添加情绪标记：[{tag}:happy/sad/angry/neutral]之一。"
            "这是可选的，如果内容不适合，可直接正常回复。此标记仅供系统参考。"
        )

    def _contains_code_content(self, text: str) -> bool:
        """检测文本是否包含代码内容"""
        if not text:
            return False
        
        code_patterns = [
            r'```[\s\S]*?```',              # 代码块
            r'`[^`\n]{3,}`',                # 较长行内代码
            r'https?://[^\s]+',             # URL链接
            r'function\s+\w+\s*\(',         # 函数定义
            r'class\s+\w+\s*[{:]',          # 类定义
            r'import\s+[\w.,\s]+',          # import语句
            r'{\s*"[\w":\s,\[\]{}]+}',      # JSON对象
        ]
        
        return any(re.search(pattern, text, re.IGNORECASE) for pattern in code_patterns)

    def _filter_code_blocks(self, text: str) -> str:
        """过滤markdown代码块和行内代码（仅替换为占位符，不删除内容）"""
        if not text:
            return text
        
        # 过滤代码块 ```代码```，替换为占位符而非删除
        text = re.sub(r'```[\s\S]*?```', '[代码块]', text)
        
        # 过滤行内代码 `代码`，替换为占位符而非删除
        text = re.sub(r'`[^`\n]+`', '[代码]', text)
        
        # 对于其他代码特征，不再删除整个文本，而是标记但保留内容
        code_patterns = [
            r'\b\w+\(\s*\)',  # 函数调用 func()
            r'\b\w+\.\w+\(',   # 方法调用 obj.method(
            r'<[^>]+>',        # HTML/XML标签
            r'\w+://\S+',      # URLs
        ]
        
        # 检测到代码特征时，保留原文但记录标记（供上层逻辑判断是否跳过TTS）
        for pattern in code_patterns:
            if re.search(pattern, text):
                logging.debug(f"_filter_code_blocks: detected code pattern {pattern}, preserving text")
                break
        
        return text

    def _filter_emoji_and_qq_expressions(self, text: str) -> str:
        """过滤emoji表情和QQ表情符号"""
        if not text:
            return text
        
        # 过滤Unicode emoji - 修正版本
        emoji_pattern = re.compile(r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F1E0-\U0001F1FF\U00002702-\U000027B0\U000024C2-\U000024FF]+')
        text = emoji_pattern.sub('', text)
        
        # 更精确的QQ表情过滤：只过滤常见的表情词汇，而不是所有中文
        qq_emotions = [
            '哈哈', '呵呵', '嘿嘿', '嘻嘻', '哭哭', '呜呜', 
            '汗', '晕', '怒', '抓狂', '吐血', '偷笑', 
            '色', '亲亲', '惊讶', '难过', '酷', '冷汗',
            '发呆', '害羞', '闭嘴', '睡觉', '大哭', '尴尬',
            '发怒', '调皮', '呲牙', '惊喜', '流汗', '憨笑'
        ]
        
        # 构建精确的QQ表情模式
        qq_emotion_pattern = '|'.join(re.escape(emotion) for emotion in qq_emotions)
        qq_pattern = re.compile(rf'\[({qq_emotion_pattern})\]')
        text = qq_pattern.sub('', text)
        
        # 过滤颜文字和ASCII艺术
        emoticon_patterns = [
            r'[><!]{2,}',      # >>>>, <<<<, !!!!
            r'[:;=][)\(DPOop]{1,}',  # :) :( :D =) ;P
            r'[)\(]{2,}',      # ))) (((
            r'[-_]{3,}',       # --- ___
        ]
        
        for pattern in emoticon_patterns:
            text = re.sub(pattern, '', text)
        
        return text.strip()

    def _deep_clean_emotion_tags(self, text: str) -> str:
        """深度清理各种形式的情绪标签"""
        if not text:
            return text
        
        # 清理各种情绪标签变体 - 修正版本，添加&符号格式支持
        patterns = [
            r'^\s*\[?\s*emo\s*[:：]?\s*\w*\s*\]?\s*[,，。:\uff1a]*\s*',  # emo: 开头
            r'^\s*\[?\s*EMO\s*[:：]?\s*\w*\s*\]?\s*[,，。:\uff1a]*\s*',  # EMO: 开头
            r'^\s*【\s*[Ee][Mm][Oo]\s*[:：]?\s*\w*\s*】\s*[,，。:\uff1a]*\s*',  # 【EMO:】
            r'\[情绪[:：]\w*\]',       # [情绪:xxx]
            r'\[心情[:：]\w*\]',       # [心情:xxx]
            r'^\s*情绪[:：]\s*\w+\s*[,，。]\s*',  # 情绪:xxx, 只清理开头的
            
            # 新增：【情绪：xxx】格式支持
            r'【情绪[:：][^】]*】',     # 【情绪：开心】等全角格式
            r'【心情[:：][^】]*】',     # 【心情：开心】等全角格式
            
            # 新增：&符号包围的情绪标签
            r'&[a-zA-Z\u4e00-\u9fff]+&',  # &英文或中文&，匹配任意位置
            r'^\s*&[a-zA-Z\u4e00-\u9fff]+&\s*[,，。:\uff1a]*\s*',  # 开头的&标签&带标点
        ]
        
        for pattern in patterns:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()

    def _ensure_proper_ending(self, text: str) -> str:
        """确保文本有适当的结尾，防止最后一个字被吞"""
        if not text or not text.strip():
            return text
        
        text = text.strip()
        
        # 如果文本不以标点符号结尾，添加句号
        if not re.search(r'[。！？.!?，,]$', text):
            # 根据内容语言添加适当的标点
            if re.search(r'[\u4e00-\u9fff]', text):  # 包含中文
                text += '。'
            else:  # 英文或其他
                text += '.'
        
        # 在结尾添加短暂停顿（通过符号实现）
        if not text.endswith('...'):
            text += '..'  # 添加额外停顿防止吞字
        
        return text

    def _final_text_cleanup(self, text: str) -> str:
        """TTS前的最终文本清理"""
        if not text:
            return text
        
        # 最后一次情绪标签清理
        text = self._deep_clean_emotion_tags(text)
        
        # 清理多余的空白字符
        text = re.sub(r'\s+', ' ', text).strip()
        
        # 移除可能导致TTS问题的字符
        problematic_chars = ['�', '\ufffd', '\x00', '\ufeff']
        for char in problematic_chars:
            text = text.replace(char, '')
        
        # 如果清理后文本为空或太短，返回空字符串跳过TTS
        if len(text.strip()) < 2:
            return ""
        
        return text

    def _strip_emo_head_many(self, text: str) -> tuple[str, Optional[str]]:
        """连续剥离多枚开头的EMO/emo标记（若LLM/其它插件重复注入）。返回(清理后文本, 最后一次解析到的情绪)。"""
        last_label: Optional[str] = None
        max_iterations = 5  # 防止无限循环
        iteration = 0
        
        while iteration < max_iterations:
            cleaned, label = self._strip_emo_head(text)
            if label:
                last_label = label
            if cleaned == text:  # 没有更多变化
                break
            text = cleaned
            iteration += 1
        
        # 额外的全局情绪标签清理
        text = self._deep_clean_emotion_tags(text)
        
        return text, last_label

    # ---------------- LLM 请求前：注入情绪标记指令 -----------------
    @filter.on_llm_request(priority=1)  # 设置较高优先级
    async def on_llm_request(self, event: AstrMessageEvent, request):
        """优化版LLM请求钩子，遵循AstrBot最佳实践"""
        if not self.emo_marker_enable:
            return
        
        try:
            # 基于官方文档：通常系统指令不会到达此钩子，但添加双重检查
            user_message = getattr(event, 'message_obj', None)
            if user_message and hasattr(user_message, 'message_str'):
                msg_content = user_message.message_str
                # 检测明显的系统指令模式
                if msg_content.startswith(('/', '!', 'tts_', '设置', '配置')):
                    logging.info("TTSEmotionRouter: 检测到疑似系统指令，跳过情绪标记")
                    return
            
            # 检查是否已注入（避免重复）
            current_prompt = getattr(request, "system_prompt", "") or ""
            if self.emo_marker_tag in current_prompt:
                return
                
            # 使用追加方式注入情绪指令（符合官方最佳实践）
            emotion_instruction = self._build_emotion_instruction()
            request.system_prompt = f"{current_prompt}\n\n{emotion_instruction}".strip()
            
            logging.info("TTSEmotionRouter: 已注入情绪标记指令")
            
        except Exception as e:
            logging.warning(f"TTSEmotionRouter.on_llm_request: {e}")

    # ---------------- LLM 标记解析（避免标签外显） -----------------
    @filter.on_llm_response(priority=1)
    async def on_llm_response(self, event: AstrMessageEvent, response: LLMResponse):
        if not self.emo_marker_enable:
            return
        label: Optional[str] = None
        cached_text: Optional[str] = None

        # 1) 尝试从 completion_text 提取并清理
        try:
            text = getattr(response, "completion_text", None)
            if isinstance(text, str) and text.strip():
                t0 = self._normalize_text(text)
                cleaned, l1 = self._strip_emo_head_many(t0)
                if l1 in EMOTIONS:
                    label = l1
                response.completion_text = cleaned
                # 兼容某些 AstrBot 内部使用 _completion_text 的实现，显式同步私有字段
                try:
                    setattr(response, "_completion_text", cleaned)
                except Exception:
                    pass
                cached_text = cleaned or cached_text
        except Exception:
            pass

        # 2) 无论 completion_text 是否为空，都从 result_chain 首个 Plain 再尝试一次
        try:
            rc = getattr(response, "result_chain", None)
            if rc and hasattr(rc, "chain") and rc.chain:
                new_chain = []
                cleaned_once = False
                for comp in rc.chain:
                    if (
                        not cleaned_once
                        and isinstance(comp, Plain)
                        and getattr(comp, "text", None)
                    ):
                        t0 = self._normalize_text(comp.text)
                        t, l2 = self._strip_emo_head_many(t0)
                        if l2 in EMOTIONS and label is None:
                            label = l2
                        if t:
                            new_chain.append(Plain(text=t))
                            # 若 completion_text 为空，则用首个 Plain 的清洗文本回填到 _completion_text
                            try:
                                if t and not getattr(response, "_completion_text", None):
                                    setattr(response, "_completion_text", t)
                            except Exception:
                                pass
                            cached_text = t or cached_text
                        cleaned_once = True
                    else:
                        new_chain.append(comp)
                rc.chain = new_chain
        except Exception:
            pass

        # 3) 记录到 session
        try:
            sid = self._sess_id(event)
            st = self._session_state.setdefault(sid, SessionState())
            if label in EMOTIONS:
                st.pending_emotion = label
            # 缓存可读文本，供只剩下 Record 的兜底入库
            if cached_text and cached_text.strip():
                st.last_assistant_text = cached_text.strip()
                st.last_assistant_text_time = time.time()
        except Exception:
            pass

        # 4) 立即尝试将清洗后的文本写入会话历史（幂等），避免后续阶段被误判 STOP 时丢上下文
        try:
            if cached_text and cached_text.strip():
                ok = await self._append_assistant_text_to_history(event, cached_text.strip())
                # 若此刻会话尚未建立，延迟一次重试
                if not ok:
                    try:
                        asyncio.create_task(self._delayed_history_write(event, cached_text.strip(), delay=0.8))
                    except Exception:
                        pass
        except Exception:
            pass

    # ---------------- Commands -----------------
    @filter.command("tts_marker_on", priority=1)
    async def tts_marker_on(self, event: AstrMessageEvent):
        self.emo_marker_enable = True
        emo_cfg = self.config.get("emotion", {}) or {}
        marker_cfg = (emo_cfg.get("marker") or {}) if isinstance(emo_cfg, dict) else {}
        marker_cfg["enable"] = True
        emo_cfg["marker"] = marker_cfg
        self.config["emotion"] = emo_cfg
        self._save_config()
        yield event.plain_result("情绪隐藏标记：开启")

    @filter.command("tts_marker_off", priority=1)
    async def tts_marker_off(self, event: AstrMessageEvent):
        self.emo_marker_enable = False
        emo_cfg = self.config.get("emotion", {}) or {}
        marker_cfg = (emo_cfg.get("marker") or {}) if isinstance(emo_cfg, dict) else {}
        marker_cfg["enable"] = False
        emo_cfg["marker"] = marker_cfg
        self.config["emotion"] = emo_cfg
        self._save_config()
        yield event.plain_result("情绪隐藏标记：关闭")

    @filter.command("tts_emote", priority=1)
    async def tts_emote(self, event: AstrMessageEvent, *, value: Optional[str] = None):
        """
        手动指定下一条消息的情绪用于路由：tts_emote happy|sad|angry|neutral
        """
        try:
            label = (value or "").strip().lower()
            assert label in EMOTIONS
            sid = self._sess_id(event)
            st = self._session_state.setdefault(sid, SessionState())
            st.pending_emotion = label
            yield event.plain_result(f"已设置：下一条消息按情绪 {label} 路由")
        except Exception:
            yield event.plain_result("用法：tts_emote <happy|sad|angry|neutral>")

    @filter.command("tts_global_on", priority=1)
    async def tts_global_on(self, event: AstrMessageEvent):
        self.global_enable = True
        self.config["global_enable"] = True
        self._save_config()
        yield event.plain_result("TTS 全局：开启（黑名单模式）")

    @filter.command("tts_global_off", priority=1)
    async def tts_global_off(self, event: AstrMessageEvent):
        self.global_enable = False
        self.config["global_enable"] = False
        self._save_config()
        yield event.plain_result("TTS 全局：关闭（白名单模式）")

    @filter.command("tts_on", priority=1)
    async def tts_on(self, event: AstrMessageEvent):
        sid = self._sess_id(event)
        if self.global_enable:
            if sid in self.disabled_sessions:
                self.disabled_sessions.remove(sid)
        else:
            if sid not in self.enabled_sessions:
                self.enabled_sessions.append(sid)
        self.config["enabled_sessions"] = self.enabled_sessions
        self.config["disabled_sessions"] = self.disabled_sessions
        self._save_config()
        yield event.plain_result("本会话TTS：开启")

    @filter.command("tts_off", priority=1)
    async def tts_off(self, event: AstrMessageEvent):
        sid = self._sess_id(event)
        if self.global_enable:
            if sid not in self.disabled_sessions:
                self.disabled_sessions.append(sid)
        else:
            if sid in self.enabled_sessions:
                self.enabled_sessions.remove(sid)
        self.config["enabled_sessions"] = self.enabled_sessions
        self.config["disabled_sessions"] = self.disabled_sessions
        self._save_config()
        yield event.plain_result("本会话TTS：关闭")

    @filter.command("tts_prob", priority=1)
    async def tts_prob(self, event: AstrMessageEvent, *, value: Optional[str] = None):
        try:
            if value is None:
                raise ValueError
            v = float(value)
            assert 0.0 <= v <= 1.0
            self.prob = v
            self.config["prob"] = v
            self._save_config()
            yield event.plain_result(f"TTS概率已设为 {v}")
        except Exception:
            yield event.plain_result("用法：tts_prob 0~1，如 0.35")

    @filter.command("tts_limit", priority=1)
    async def tts_limit(self, event: AstrMessageEvent, *, value: Optional[str] = None):
        try:
            if value is None:
                raise ValueError
            v = int(value)
            assert v >= 0
            self.text_limit = v
            self.config["text_limit"] = v
            self._save_config()
            yield event.plain_result(f"TTS字数上限已设为 {v}")
        except Exception:
            yield event.plain_result("用法：tts_limit <非负整数>")

    @filter.command("tts_cooldown", priority=1)
    async def tts_cooldown(
        self, event: AstrMessageEvent, *, value: Optional[str] = None
    ):
        try:
            if value is None:
                raise ValueError
            v = int(value)
            assert v >= 0
            self.cooldown = v
            self.config["cooldown"] = v
            self._save_config()
            yield event.plain_result(f"TTS冷却时间已设为 {v}s")
        except Exception:
            yield event.plain_result("用法：tts_cooldown <非负整数(秒)>")

    @filter.command("tts_test", priority=1)
    async def tts_test(self, event: AstrMessageEvent, *, text: Optional[str] = None):
        """测试TTS功能并诊断问题。用法：tts_test [测试文本]"""
        if not text:
            text = "你好，这是一个TTS测试"
        
        sid = self._sess_id(event)
        if not self._is_session_enabled(sid):
            yield event.plain_result("本会话TTS未启用，请使用 tts_on 启用")
            return
        
        try:
            # 选择默认情绪和音色
            emotion = "neutral"
            vkey, voice = self._pick_voice_for_emotion(emotion)
            if not voice:
                yield event.plain_result(f"错误：未配置音色映射，请先配置 voice_map.{emotion}")
                return
            
            # 创建输出目录
            out_dir = TEMP_DIR / sid
            ensure_dir(out_dir)
            
            # 生成音频
            yield event.plain_result(f"正在生成测试音频：\"{text}\"...")
            
            # 添加文本预处理诊断
            original_text = text
            normalized_text = self._normalize_text(text)
            cleaned_text, _ = self._strip_emo_head_many(normalized_text)
            final_text = self._final_text_cleanup(cleaned_text)
            processed_text = self._ensure_proper_ending(final_text)
            
            # 显示文本处理过程
            if original_text != processed_text:
                yield event.plain_result(f"📝 文本预处理过程：\n原始: \"{original_text}\"\n处理后: \"{processed_text}\"")
            
            # 使用处理后的文本进行测试
            text = processed_text
            
            start_time = time.time()
            audio_path = self.tts.synth(text, voice, out_dir, speed=None)
            generation_time = time.time() - start_time
            
            if not audio_path:
                yield event.plain_result("❌ TTS API调用失败")
                return
            
            # 验证文件
            if not self._validate_audio_file(audio_path):
                yield event.plain_result(f"❌ 生成的音频文件无效: {audio_path}")
                return
            
            # 路径规范化测试
            normalized_path = self._normalize_audio_path(audio_path)
            
            # 尝试创建Record对象
            try:
                record = Record(file=normalized_path)
                record_status = "✅ 成功"
            except Exception as e:
                record_status = f"❌ 失败: {e}"
            
            # 报告结果
            file_size = audio_path.stat().st_size
            result_msg = f"""🎵 TTS测试结果：
✅ 音频生成成功
📁 文件路径: {audio_path.name}
📊 文件大小: {file_size} 字节
⏱️ 生成耗时: {generation_time:.2f}秒
🎯 使用音色: {vkey} ({voice[:30]}...)
📝 Record对象: {record_status}
🔧 规范化路径: {normalized_path == str(audio_path)}"""
            
            yield event.plain_result(result_msg)
            
            # 尝试发送音频
            try:
                yield event.record_result(str(audio_path))
            except Exception as e:
                yield event.plain_result(f"❌ 音频发送失败: {e}")
            
        except Exception as e:
            yield event.plain_result(f"❌ TTS测试失败: {e}")
            logging.error(f"TTS测试异常: {e}", exc_info=True)

    @filter.command("tts_debug", priority=1)
    async def tts_debug(self, event: AstrMessageEvent):
        """显示TTS调试信息"""
        try:
            sid = self._sess_id(event)
            st = self._session_state.get(sid, SessionState())
            
            # 系统信息
            import platform
            import os
            
            debug_info = f"""🔧 TTS调试信息：
🖥️ 系统: {platform.system()} {platform.release()}
📂 Python路径: {os.getcwd()}
🆔 会话ID: {sid}
⚡ 会话状态: {'✅ 启用' if self._is_session_enabled(sid) else '❌ 禁用'}
🎛️ 全局开关: {'✅ 开启' if self.global_enable else '❌ 关闭'}
🎲 触发概率: {self.prob}
📏 文字限制: {self.text_limit}
⏰ 冷却时间: {self.cooldown}s
🔄 混合内容: {'✅ 允许' if self.allow_mixed else '❌ 禁止'}
🎵 API模型: {self.tts.model}
🎚️ 音量增益: {self.tts.gain}dB
📁 临时目录: {TEMP_DIR}

📊 会话统计:
🕐 最后TTS时间: {time.strftime('%H:%M:%S', time.localtime(st.last_tts_time)) if st.last_tts_time else '无'}
📝 最后TTS内容: {st.last_tts_content[:30] + '...' if st.last_tts_content and len(st.last_tts_content) > 30 else st.last_tts_content or '无'}
😊 待用情绪: {st.pending_emotion or '无'}

🎭 音色配置:"""
            
            for emotion in EMOTIONS:
                vkey, voice = self._pick_voice_for_emotion(emotion)
                speed = self.speed_map.get(emotion) if isinstance(self.speed_map, dict) else None
                debug_info += f"\n{emotion}: {vkey if voice else '❌ 未配置'}"
                if speed:
                    debug_info += f" (语速: {speed})"
            
            yield event.plain_result(debug_info)
            
        except Exception as e:
            yield event.plain_result(f"❌ 获取调试信息失败: {e}")

    @filter.command("tts_test_problematic", priority=1)
    async def tts_test_problematic(self, event: AstrMessageEvent):
        """测试各种问题文本的处理效果"""
        try:
            # 测试用例：各种可能导致问题的文本
            test_cases = [
                "[EMO:happy] 这是带情绪标签的文本",
                "【EMO：sad】这是全角情绪标签",  
                "emo:angry 这是简化情绪标签",
                "```python\nprint('hello')\n``` 这里有代码块",
                "`console.log()` 行内代码测试",
                "😀😢😡 emoji表情测试",
                "[哈哈][呵呵] QQ表情测试", 
                "function test() {} 代码特征测试",
                ">>> 特殊符号测试 <<<",
                ":) :( :D 颜文字测试",
                "没有标点的文本",
                
                # 新增：&符号情绪标签测试
                "&shy& 这是害羞的表情",
                "&开心& 今天天气很好",
                "&happy& 测试英文情绪",
                "&angry& 很生气的消息",
                "text &sad& more text",
                "&unknown& 未知情绪测试",
                "R&D部门 & 运营部门",  # 确保不误删正常&使用
            ]
            
            result_msg = "🧪 问题文本处理测试结果：\n\n"
            
            for i, test_text in enumerate(test_cases, 1):
                # 执行完整的文本处理流程
                try:
                    original = test_text
                    normalized = self._normalize_text(test_text)
                    cleaned, emotion = self._strip_emo_head_many(normalized)
                    final_cleaned = self._deep_clean_emotion_tags(cleaned)
                    final_text = self._final_text_cleanup(final_cleaned)
                    ended_text = self._ensure_proper_ending(final_text)
                    
                    # 记录处理结果
                    result_msg += f"{i}. 测试: {original[:30]}{'...' if len(original) > 30 else ''}\n"
                    if original != ended_text:
                        result_msg += f"   处理后: {ended_text[:30]}{'...' if len(ended_text) > 30 else ''}\n"
                        if emotion:
                            result_msg += f"   检测情绪: {emotion}\n"
                        result_msg += f"   状态: {'✅ 可转TTS' if ended_text and len(ended_text.strip()) >= 2 else '❌ 已过滤'}\n"
                    else:
                        result_msg += f"   状态: ✅ 无需处理\n"
                    result_msg += "\n"
                    
                except Exception as e:
                    result_msg += f"   ❌ 处理异常: {e}\n\n"
            
            yield event.plain_result(result_msg)
            
        except Exception as e:
            yield event.plain_result(f"❌ 测试失败: {e}")

    @filter.command("tts_gain", priority=1)
    async def tts_gain(self, event: AstrMessageEvent, *, value: Optional[str] = None):
        """调节输出音量增益（单位dB，范围 -10 ~ 10）。示例：tts_gain 5"""
        try:
            if value is None:
                raise ValueError
            v = float(value)
            assert -10.0 <= v <= 10.0
            # 更新运行期
            try:
                self.tts.gain = v
            except Exception:
                pass
            # 持久化
            api_cfg = self.config.get("api", {}) or {}
            api_cfg["gain"] = v
            self.config["api"] = api_cfg
            self._save_config()
            yield event.plain_result(f"TTS音量增益已设为 {v} dB")
        except Exception:
            yield event.plain_result("用法：tts_gain <-10~10>，例：tts_gain 5")

    @filter.command("tts_status", priority=1)
    async def tts_status(self, event: AstrMessageEvent):
        sid = self._sess_id(event)
        mode = "黑名单(默认开)" if self.global_enable else "白名单(默认关)"
        enabled = self._is_session_enabled(sid)
        yield event.plain_result(
            f"模式: {mode}\n当前会话: {'启用' if enabled else '禁用'}\nprob={self.prob}, limit={self.text_limit}, cooldown={self.cooldown}s\nallow_mixed={self.allow_mixed}, smart_detection={'开启' if self.smart_detection else '关闭'}"
        )

    @filter.command("tts_mixed_on", priority=1)
    async def tts_mixed_on(self, event: AstrMessageEvent):
        """允许混合输出（文本+语音都保留）"""
        self.allow_mixed = True
        try:
            if self.config is not None and (
                isinstance(self.config, AstrBotConfig) or isinstance(self.config, dict)
            ):
                self.config["allow_mixed"] = True
                self._save_config()
        except Exception:
            pass
        yield event.plain_result("TTS混合输出：开启（文本+语音）")

    @filter.command("tts_mixed_off", priority=1)
    async def tts_mixed_off(self, event: AstrMessageEvent):
        """仅纯文本可参与合成；含图片/回复等时跳过"""
        self.allow_mixed = False
        try:
            if self.config is not None and (
                isinstance(self.config, AstrBotConfig) or isinstance(self.config, dict)
            ):
                self.config["allow_mixed"] = False
                self._save_config()
        except Exception:
            pass
        yield event.plain_result("TTS混合输出：关闭（仅纯文本时尝试合成）")

    @filter.command("tts_smart_on", priority=1)
    async def tts_smart_on(self, event: AstrMessageEvent):
        """启用智能检测：自动识别代码内容并跳过TTS，保留文本输出"""
        self.smart_detection = True
        try:
            if self.config is not None and (
                isinstance(self.config, AstrBotConfig) or isinstance(self.config, dict)
            ):
                self.config["smart_detection"] = True
                self._save_config()
        except Exception:
            pass
        yield event.plain_result("TTS智能检测：开启（代码内容将跳过语音转换，保留文本）")

    @filter.command("tts_smart_off", priority=1)
    async def tts_smart_off(self, event: AstrMessageEvent):
        """关闭智能检测：所有内容都尝试TTS转换（传统模式）"""
        self.smart_detection = False
        try:
            if self.config is not None and (
                isinstance(self.config, AstrBotConfig) or isinstance(self.config, dict)
            ):
                self.config["smart_detection"] = False
                self._save_config()
        except Exception:
            pass
        yield event.plain_result("TTS智能检测：关闭（所有文本都将尝试语音转换）")

    # ---------------- After send hook: 防止重复 RespondStage 再次发送 -----------------
    # 兼容不同 AstrBot 版本：优先使用 after_message_sent，其次回退 on_after_message_sent；都没有则不挂载该钩子。
    if hasattr(filter, "after_message_sent"):
        @filter.after_message_sent(priority=-1000)
        async def after_message_sent(self, event: AstrMessageEvent):
            # 仅记录诊断信息，不再清空链，避免影响历史写入/上下文。
            try:
                # 确保不被判定为终止传播
                try:
                    event.continue_event()
                except Exception:
                    pass
                try:
                    res = event.get_result()
                    # 只读，不创建/修改 result，避免触发重复发送
                    if res is not None and hasattr(res, "continue_event"):
                        res.continue_event()
                except Exception:
                    pass
                try:
                    logging.debug("TTSEmotionRouter.after_message_sent: entry is_stopped=%s", event.is_stopped())
                except Exception:
                    pass
                result = event.get_result()
                if not result or not getattr(result, "chain", None):
                    return
                try:
                    has_plain = any(isinstance(c, Plain) for c in result.chain)
                    has_record = any(isinstance(c, Record) for c in result.chain)
                    logging.info(
                        "after_message_sent: snapshot len=%d, has_plain=%s, has_record=%s, is_llm=%s",
                        len(result.chain), has_plain, has_record, getattr(result, "result_content_type", None) == ResultContentType.LLM_RESULT,
                    )
                except Exception:
                    pass
                # 兜底：若为 LLM 结果且包含任意语音（不局限于本插件），确保将可读文本写入对话历史
                try:
                    if any(isinstance(c, Record) for c in result.chain):
                        await self._ensure_history_saved(event)
                except Exception:
                    pass
                # 再次声明继续传播
                try:
                    event.continue_event()
                except Exception:
                    pass
                try:
                    res = event.get_result()
                    if res is not None and hasattr(res, "continue_event"):
                        res.continue_event()
                except Exception:
                    pass
                # 兼容部分框架对“未产出/未修改”的停止判定，进行一次无害的 get_result 访问
                try:
                    _ = event.get_result()
                except Exception:
                    pass
                try:
                    logging.debug("TTSEmotionRouter.after_message_sent: exit is_stopped=%s", event.is_stopped())
                except Exception:
                    pass
            except Exception:
                pass
    elif hasattr(filter, "on_after_message_sent"):
        @filter.on_after_message_sent(priority=-1000)
        async def after_message_sent(self, event: AstrMessageEvent):
            # 仅记录诊断信息，不再清空链，避免影响历史写入/上下文。
            try:
                # 确保不被判定为终止传播
                try:
                    event.continue_event()
                except Exception:
                    pass
                try:
                    res = event.get_result()
                    # 只读，不创建/修改 result，避免触发重复发送
                    if res is not None and hasattr(res, "continue_event"):
                        res.continue_event()
                except Exception:
                    pass
                try:
                    logging.debug("TTSEmotionRouter.after_message_sent: entry(is_compat) is_stopped=%s", event.is_stopped())
                except Exception:
                    pass
                result = event.get_result()
                if not result or not getattr(result, "chain", None):
                    return
                try:
                    has_plain = any(isinstance(c, Plain) for c in result.chain)
                    has_record = any(isinstance(c, Record) for c in result.chain)
                    logging.info(
                        "after_message_sent: snapshot len=%d, has_plain=%s, has_record=%s, is_llm=%s",
                        len(result.chain), has_plain, has_record, getattr(result, "result_content_type", None) == ResultContentType.LLM_RESULT,
                    )
                except Exception:
                    pass
                # 兜底：若为 LLM 结果且包含任意语音（不局限于本插件），确保将可读文本写入对话历史
                try:
                    if any(isinstance(c, Record) for c in result.chain):
                        await self._ensure_history_saved(event)
                except Exception:
                    pass
                # 再次声明继续传播
                try:
                    event.continue_event()
                except Exception:
                    pass
                try:
                    res = event.get_result()
                    if res is not None and hasattr(res, "continue_event"):
                        res.continue_event()
                except Exception:
                    pass
                # 兼容部分框架对“未产出/未修改”的停止判定，进行一次无害的 get_result 访问
                try:
                    _ = event.get_result()
                except Exception:
                    pass
                try:
                    logging.debug("TTSEmotionRouter.after_message_sent: exit(is_compat) is_stopped=%s", event.is_stopped())
                except Exception:
                    pass
            except Exception:
                pass
    else:
        async def after_message_sent(self, event: AstrMessageEvent):
            return

    # ---------------- Core hook -----------------
    @filter.on_decorating_result(priority=-1000)
    async def on_decorating_result(self, event: AstrMessageEvent):
        """TTS 情绪路由处理 - 简化版本，确保事件传播正常"""
        
        # 早期检查和跳过条件
        sid = self._sess_id(event)
        if not self._is_session_enabled(sid):
            logging.info("TTS skip: session disabled (%s)", sid)
            event.continue_event()
            return

        result = event.get_result()
        if not result or not result.chain:
            logging.debug("TTS skip: empty result chain")
            event.continue_event()
            return

        # 检查是否为命令回复，如果是则跳过TTS处理
        if self._is_command_input(event):
            logging.info("TTS skip: detected command input, preserving text-only output")
            event.continue_event()
            return

        # 清理首个 Plain 的隐藏情绪头 - 增强版本
        try:
            new_chain = []
            cleaned_once = False
            for comp in result.chain:
                if (
                    not cleaned_once
                    and isinstance(comp, Plain)
                    and getattr(comp, "text", None)
                ):
                    t0 = self._normalize_text(comp.text)
                    # 多层清理
                    t, _ = self._strip_emo_head_many(t0)
                    t = self._deep_clean_emotion_tags(t)  # 新增深度清理
                    if t:
                        new_chain.append(Plain(text=t))
                    cleaned_once = True
                else:
                    new_chain.append(comp)
            result.chain = new_chain
        except Exception:
            pass

        # 是否允许混合
        if not self.allow_mixed and any(not isinstance(c, Plain) for c in result.chain):
            logging.info("TTS skip: mixed content not allowed (allow_mixed=%s)", self.allow_mixed)
            event.continue_event()
            return

        # 拼接纯文本
        text_parts = [
            c.text.strip()
            for c in result.chain
            if isinstance(c, Plain) and c.text.strip()
        ]
        if not text_parts:
            logging.debug("TTS skip: no plain text parts after cleaning")
            event.continue_event()
            return
        text = " ".join(text_parts)

        # 归一化 + 连续剥离（终极兜底）
        orig_text = text
        text = self._normalize_text(text)
        text, _ = self._strip_emo_head_many(text)

        # 过滤链接/文件等提示性内容，避免朗读
        if re.search(r"(https?://|www\.|\[图片\]|\[文件\]|\[转发\]|\[引用\])", text, re.I):
            logging.info("TTS skip: detected link/attachment tokens")
            event.continue_event()
            return
        
        # 智能检测代码内容，跳过TTS但保留文本输出（可配置）
        if self.smart_detection and self._contains_code_content(text):
            logging.info("TTS skip: smart detection found code content, preserving text output")
            # 保持原始文本输出，不进行TTS转换
            event.continue_event()
            return

        # 检查冷却、长度限制、概率
        st = self._session_state.setdefault(sid, SessionState())
        now = time.time()
        if self.cooldown > 0 and (now - st.last_ts) < self.cooldown:
            logging.info("TTS skip: cooldown active (%.2fs < %ss)", now - st.last_ts, self.cooldown)
            event.continue_event()
            return

        if self.text_limit > 0 and len(text) > self.text_limit:
            logging.info("TTS skip: over text_limit (len=%d > limit=%d)", len(text), self.text_limit)
            event.continue_event()
            return

        if random.random() > self.prob:
            logging.info("TTS skip: probability gate (prob=%.2f)", self.prob)
            event.continue_event()
            return

        # 情绪选择：优先使用隐藏标记 -> 启发式
        if st.pending_emotion in EMOTIONS:
            emotion = st.pending_emotion
            st.pending_emotion = None
            src = "tag"
        else:
            emotion = self.heuristic_cls.classify(text, context=None)
            src = "heuristic"
            try:
                kw = getattr(self, "_emo_kw", {})
                has_kw = any(p.search(text) for p in kw.values())
                if not has_kw:
                    emotion = "neutral"
            except Exception:
                pass

        vkey, voice = self._pick_voice_for_emotion(emotion)
        if not voice:
            logging.warning("No voice mapped for emotion=%s", emotion)
            event.continue_event()
            return

        speed_override = None
        try:
            if isinstance(self.speed_map, dict):
                v = self.speed_map.get(emotion)
                if v is None:
                    v = self.speed_map.get("neutral")
                if v is not None:
                    speed_override = float(v)
        except Exception:
            speed_override = None

        logging.info(
            "TTS route: emotion=%s(src=%s) -> %s (%s), speed=%s",
            emotion,
            src,
            vkey,
            (voice[:40] + "...") if isinstance(voice, str) and len(voice) > 43 else voice,
            speed_override if speed_override is not None else getattr(self.tts, "speed", None),
        )
        logging.debug("TTS input head(before/after): %r -> %r", orig_text[:60], text[:60])

        out_dir = TEMP_DIR / sid
        ensure_dir(out_dir)

        # 最后一重防线：若 TTS 前文本仍以 emo/token 开头，强制清理
        try:
            if text and (text.lower().lstrip().startswith("emo") or text.lstrip().startswith(("[", "【", "("))):
                text, _ = self._strip_emo_head_many(text)
        except Exception:
            pass

        # TTS合成前的最终文本处理
        try:
            # 最终清理各种遗留的情绪标签和特殊内容
            text = self._final_text_cleanup(text)
            
            # 防止最后一个字被吞：确保文本以适当的标点结尾
            text = self._ensure_proper_ending(text)
            
            # 如果清理后文本为空，跳过TTS
            if not text or len(text.strip()) < 2:
                logging.info("TTS skip: text empty after final cleanup")
                event.continue_event()
                return
                
        except Exception:
            pass

        # TTS 合成和处理
        audio_path = self.tts.synth(text, voice, out_dir, speed=speed_override)
        if not audio_path:
            logging.error("TTS调用失败，降级为文本")
            event.continue_event()
            return

        # 验证生成的音频文件
        if not self._validate_audio_file(audio_path):
            logging.error(f"TTS生成的音频文件无效: {audio_path}")
            # 直接回退到文本，不发送无效音频
            result.chain = [Plain(text=text)]
            event.continue_event()
            return
        
        # 使用相对路径以提高兼容性
        try:
            import os
            work_dir = Path(os.getcwd())
            try:
                relative_path = audio_path.relative_to(work_dir)
                audio_file_path = str(relative_path).replace('\\', '/')
                logging.info(f"TTS: 使用相对路径: {audio_file_path}")
            except ValueError:
                # 如果无法计算相对路径，使用绝对路径
                audio_file_path = str(audio_path).replace('\\', '/')
                logging.info(f"TTS: 使用绝对路径: {audio_file_path}")
        except Exception:
            audio_file_path = str(audio_path)
        
        # 创建Record对象前进行最后验证
        try:
            # 确保文件存在且可读
            test_path = Path(audio_file_path) if not Path(audio_file_path).is_absolute() else audio_path
            if not test_path.exists():
                raise FileNotFoundError(f"音频文件不存在: {test_path}")
            
            # 检查文件大小
            file_size = test_path.stat().st_size
            if file_size == 0:
                raise ValueError(f"音频文件为空: {test_path}")
            
            logging.info(f"TTS: 音频文件验证通过，大小={file_size}字节")
            
        except Exception as e:
            logging.error(f"TTS: 音频文件验证失败: {e}")
            # 验证失败时回退到纯文本
            result.chain = [Plain(text=text)]
            event.continue_event()
            return
        
        # 创建Record并更新结果
        try:
            record = Record(file=audio_file_path)
            logging.info(f"TTS: 成功创建Record对象，路径={audio_file_path}")
            
            # 更新会话状态
            st.last_tts_content = text
            st.last_tts_time = time.time()
            st.last_ts = time.time()

            # 根据配置决定输出格式
            if self.allow_mixed:
                result.chain = [Plain(text=text), record]
                logging.info("TTS: 输出混合内容（文本+音频）")
            else:
                result.chain = [record]
                logging.info("TTS: 输出纯音频")
            
            # 记录成功信息
            logging.info(f"TTS: 音频处理完成 - 文件={audio_path.name}, 大小={file_size}字节")
            
        except Exception as e:
            logging.error(f"TTS: 创建Record失败: {e}")
            # Record创建失败，强制回退到文本
            result.chain = [Plain(text=text)]
            logging.info("TTS: 已回退到纯文本输出")

        # 后续处理
        try:
            _hp = any(isinstance(c, Plain) for c in result.chain)
            _hr = any(isinstance(c, Record) for c in result.chain)
            logging.info("TTS finalize: has_plain=%s, has_record=%s, text_len=%d", _hp, _hr, len(text))
        except Exception:
            pass

        try:
            _ = await self._append_assistant_text_to_history(event, text)
        except Exception:
            pass
            
        try:
            st.last_assistant_text = text.strip()
            st.last_assistant_text_time = time.time()
        except Exception:
            pass
            
        try:
            result.set_result_content_type(ResultContentType.LLM_RESULT)
        except Exception:
            pass

        # 确保事件继续传播
        event.continue_event()

    async def _ensure_history_saved(self, event: AstrMessageEvent) -> None:
        """兜底：保证本轮助手可读文本写入到会话历史。
        条件：当前结果被标记为 LLM_RESULT，且链中含有本插件生成的 Record。
        逻辑：聚合链中的 Plain 文本；若历史最后的 assistant 文本不等于该文本，则补记一条。
        """
        try:
            result = event.get_result()
            if not result or not getattr(result, "chain", None):
                return
            # 兼容不同 AstrBot 版本：若无法判断 is_llm_result，则仅以“链中含本插件音频”为条件。
            is_llm = False
            try:
                is_llm = bool(result.is_llm_result())
            except Exception:
                is_llm = False
            if not is_llm and not any(self._is_our_record(c) for c in result.chain):
                return
            # 聚合文本
            parts = []
            for comp in result.chain:
                if isinstance(comp, Plain) and getattr(comp, "text", None):
                    t = comp.text.strip()
                    if t:
                        parts.append(t)
            text = "\n".join(parts).strip()
            if not text:
                # 若链中没有文本，回退使用缓存
                try:
                    sid = self._sess_id(event)
                    st = self._session_state.setdefault(sid, SessionState())
                    if st.last_assistant_text and (time.time() - st.last_assistant_text_time) < 60:
                        await self._append_assistant_text_to_history(event, st.last_assistant_text)
                except Exception:
                    pass
                return
            await self._append_assistant_text_to_history(event, text)
        except Exception:
            # 容错：不因兜底写入失败影响主流程
            pass

    async def _append_assistant_text_to_history(self, event: AstrMessageEvent, text: str) -> bool:
        """使用已清洗的最终文本，直接写入会话历史（去重且幂等）。返回是否成功写入。"""
        if not text:
            return False
        try:
            cm = self.context.conversation_manager
            uid = event.unified_msg_origin
            # 获取会话ID：优先 provider_request，其次当前活跃会话；若暂不可用，小退避重试
            cid = None
            for attempt in range(3):
                try:
                    req = getattr(event, "get_extra", None) and event.get_extra("provider_request")
                    if req and getattr(req, "conversation", None) and getattr(req.conversation, "cid", None):
                        cid = req.conversation.cid
                except Exception:
                    cid = None
                if not cid:
                    try:
                        cid = await cm.get_curr_conversation_id(uid)
                    except Exception:
                        cid = None
                if cid:
                    break
                # 等待会话在核心落库
                await asyncio.sleep(0.2)
            if not cid:
                logging.info("TTSEmotionRouter.history_fallback: skip write, no active conversation id after retry")
                return False
            # 获取会话体，优先不创建；若仍未就绪，小退避后允许创建一次，避免错过本轮文本
            conv = await cm.get_conversation(uid, cid, create_if_not_exists=False)
            if not conv:
                await asyncio.sleep(0.2)
                try:
                    conv = await cm.get_conversation(uid, cid, create_if_not_exists=True)
                except Exception:
                    conv = None
            if not conv:
                logging.info("TTSEmotionRouter.history_fallback: conversation still not available for cid=%s", cid)
                return False
            import json as _json
            msgs = []
            try:
                msgs = _json.loads(conv.history) if getattr(conv, "history", "") else []
            except Exception:
                msgs = []

            # 若最后一个 assistant 文本已相同，则不重复写入
            if msgs:
                last = msgs[-1]
                if isinstance(last, dict) and last.get("role") == "assistant" and (last.get("content") or "").strip() == text.strip():
                    return True

            msgs.append({"role": "assistant", "content": text.strip()})
            await cm.update_conversation(uid, cid, history=msgs)
            logging.info("TTSEmotionRouter.history_fallback: appended assistant text to conversation history")
            return True
        except Exception:
            return False

    async def _delayed_history_write(self, event: AstrMessageEvent, text: str, delay: float = 0.8):
        """延迟写入一次会话历史，避免 on_llm_response 时会话尚未建立导致的落库失败。"""
        try:
            await asyncio.sleep(max(0.0, float(delay)))
            await self._append_assistant_text_to_history(event, text)
        except Exception:
            pass
