from typing import List, Optional, Dict
import re

EMOTIONS = ["neutral", "happy", "sad", "angry"]

# 极简启发式情绪分类器，避免引入大模型依赖；后续可替换为 onnx 推理
POS_WORDS = {"开心", "高兴", "喜欢", "太棒了", "哈哈", "lol", ":)", "😀"}
NEG_WORDS = {"难过", "伤心", "失望", "糟糕", "无语", "唉", "sad", ":(", "😢"}
ANG_WORDS = {"气死", "愤怒", "生气", "nm", "tmd", "淦", "怒", "怒了", "😡"}

URL_RE = re.compile(r"https?://|www\.")


def is_informational(text: str) -> bool:
    # 包含链接/代码/文件提示等，视为信息性，倾向 neutral
    return bool(URL_RE.search(text or ""))


def classify(text: str, context: Optional[List[str]] = None) -> str:
    t = (text or "").lower()
    score: Dict[str, float] = {"happy": 0.0, "sad": 0.0, "angry": 0.0}

    # 简单计数词典命中
    for w in POS_WORDS:
        if w.lower() in t:
            score["happy"] += 1.0
    for w in NEG_WORDS:
        if w.lower() in t:
            score["sad"] += 1.0
    for w in ANG_WORDS:
        if w.lower() in t:
            score["angry"] += 1.0

    # 感叹号、全大写等作为情绪增强
    if text and "!" in text:
        score["angry"] += 1.0
    if (
        text
        and text.strip()
        and text == text.upper()
        and any(c.isalpha() for c in text)
    ):
        score["angry"] += 1.0

    # 上下文弱加权
    if context:
        ctx = "\n".join(context[-3:]).lower()
        for w in POS_WORDS:
            if w.lower() in ctx:
                score["happy"] += 0.3
        for w in NEG_WORDS:
            if w.lower() in ctx:
                score["sad"] += 0.3
        for w in ANG_WORDS:
            if w.lower() in ctx:
                score["angry"] += 0.3

    if is_informational(text or ""):
        return "neutral"

    # 选最大，否则中性
    label = max(score.keys(), key=lambda k: score[k])
    if score[label] <= 0:
        return "neutral"
    return label
