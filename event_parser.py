"""
event_parser.py
AutoBangumi Webhook 事件解析模块。

职责：
    接收 AutoBangumi 的 webhook JSON 原始数据，识别事件类型并提取结构化字段，
    生成人类可读的通知摘要文本。

支持的 AutoBangumi 模板变量：
    {{title}}         番剧标题
    {{season}}        季度
    {{episode}}       集数
    {{poster_url}}    海报图片 URL
    {{torrent_name}}  种子文件名
    {{file_name}}     下载后的文件名
    {{size}}          文件大小
    {{error_msg}}     错误信息（下载/RSS 失败时）
    {{message}}       通用消息文本
    {{event}}         事件类型标识

作者：yometenma
版本：1.2.0
"""

import hashlib
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class EventType(str, Enum):
    """AutoBangumi 通知事件类型。"""
    NEW_EPISODE = "new_episode"           # 新番更新（RSS 抓取到新集）
    DOWNLOAD_START = "download_start"     # 开始下载
    DOWNLOAD_COMPLETE = "download_complete"  # 下载完成
    RENAME_COMPLETE = "rename_complete"   # 重命名/刮削完成（导入媒体库）
    DOWNLOAD_ERROR = "download_error"     # 下载失败
    RSS_ERROR = "rss_error"               # RSS 解析/抓取异常
    UNKNOWN = "unknown"                   # 无法识别的类型


@dataclass
class ParsedEvent:
    """解析后的通知事件结构。"""
    raw: dict = field(repr=False)                               # 原始 JSON
    event_type: EventType = EventType.UNKNOWN                   # 事件类型
    title: Optional[str] = None                                 # 番剧标题
    season: Optional[int] = None                                # 季度
    episode: Optional[int] = None                               # 集数
    poster_url: Optional[str] = None                            # 海报图 URL
    torrent_name: Optional[str] = None                          # 种子文件名
    file_name: Optional[str] = None                             # 成品文件名
    size: Optional[str] = None                                  # 文件大小
    error_msg: Optional[str] = None                             # 错误信息
    message: Optional[str] = None                               # 通用消息
    extra: dict = field(default_factory=dict)                   # 其他字段

    def content_fingerprint(self) -> str:
        """生成内容指纹（用于去重），只看业务字段，不看时间戳等易变字段。"""
        key_data = f"{self.title}|{self.season}|{self.episode}|{self.event_type}"
        return hashlib.sha256(key_data.encode("utf-8")).hexdigest()


def parse_event(raw: dict) -> ParsedEvent:
    """从 webhook 原始 JSON 中解析出 ParsedEvent。

    支持以下识别策略（按优先级）：
    1. 显式 event/type/event_type 字段
    2. 根据字段组合推断（有 error_msg → 错误类，download/rename 相关 → 对应类型）
    3. 兜底为 UNKNOWN
    """
    event = ParsedEvent(raw=raw)

    # ---- 基础字段提取 ----
    event.title = raw.get("title") or raw.get("official_title") or raw.get("name")
    event.poster_url = raw.get("poster_url") or raw.get("poster")
    event.torrent_name = raw.get("torrent_name") or raw.get("torrent")
    event.file_name = raw.get("file_name") or raw.get("filename")
    event.size = raw.get("size") or raw.get("file_size")
    event.error_msg = raw.get("error_msg") or raw.get("error") or raw.get("err_msg")
    event.message = raw.get("message") or raw.get("msg")
    event.season = _parse_int(raw.get("season"))
    event.episode = _parse_int(raw.get("episode"))

    # 收集其他未显式处理的字段
    known_keys = {
        "title", "official_title", "name",
        "season", "episode",
        "poster_url", "poster",
        "torrent_name", "torrent",
        "file_name", "filename",
        "size", "file_size",
        "error_msg", "error", "err_msg",
        "message", "msg",
        "event", "type", "event_type", "notify_type",
    }
    event.extra = {k: v for k, v in raw.items() if k not in known_keys}

    # ---- 事件类型识别 ----
    event.event_type = _classify_event(raw, event)

    return event


def build_notification_text(event: ParsedEvent) -> str:
    """根据解析后的事件生成人类可读的中文摘要文本。

    注意：这个文本是「原始通知摘要」，不是 LLM 转述后的结果。
    LLM 会把这个摘要作为 prompt 输入，用机器人人设重新表述。
    """
    t = event.title or "未知番剧"

    if event.event_type == EventType.NEW_EPISODE:
        text = f"番剧《{t}》"
        if event.season is not None:
            text += f" 第{event.season}季"
        if event.episode is not None:
            text += f" 第{event.episode}集"
        text += " 有更新"
        return text

    if event.event_type == EventType.DOWNLOAD_START:
        text = f"番剧《{t}》开始下载"
        if event.season is not None and event.episode is not None:
            text += f" S{event.season:02d}E{event.episode:02d}"
        if event.torrent_name:
            text += f"（种子: {event.torrent_name}）"
        return text

    if event.event_type == EventType.DOWNLOAD_COMPLETE:
        text = f"番剧《{t}》下载完成"
        if event.season is not None and event.episode is not None:
            text += f" S{event.season:02d}E{event.episode:02d}"
        if event.size:
            text += f"（大小: {event.size}）"
        return text

    if event.event_type == EventType.RENAME_COMPLETE:
        text = f"番剧《{t}》已整理完成"
        if event.file_name:
            text += f" → {event.file_name}"
        return text

    if event.event_type == EventType.DOWNLOAD_ERROR:
        text = f"番剧《{t}》下载失败"
        if event.error_msg:
            text += f"：{event.error_msg}"
        return text

    if event.event_type == EventType.RSS_ERROR:
        text = "RSS 抓取异常"
        if event.error_msg:
            text += f"：{event.error_msg}"
        elif event.message:
            text += f"：{event.message}"
        return text

    # UNKNOWN 或未匹配的类型：尽力拼出可读文本
    if event.title:
        text = f"番剧《{event.title}》通知"
        if event.message:
            text += f"：{event.message}"
        elif event.error_msg:
            text += f"：{event.error_msg}"
        return text

    if event.message:
        return event.message
    if event.error_msg:
        return f"错误通知：{event.error_msg}"

    # 最后兜底：转 JSON
    import json
    return json.dumps(event.raw, ensure_ascii=False, default=str)


# ========== 内部辅助函数 ==========

def _parse_int(value) -> Optional[int]:
    """安全地将值转为整数，失败返回 None。"""
    if value is None:
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def _classify_event(raw: dict, event: ParsedEvent) -> EventType:
    """根据 JSON 字段识别事件类型。"""

    # 1. 显式字段
    explicit = raw.get("event") or raw.get("type") or raw.get("event_type") or raw.get("notify_type")
    if explicit:
        explicit_lower = str(explicit).lower().strip()
        mapping = {
            "new_episode": EventType.NEW_EPISODE,
            "new": EventType.NEW_EPISODE,
            "update": EventType.NEW_EPISODE,
            "download_start": EventType.DOWNLOAD_START,
            "download_started": EventType.DOWNLOAD_START,
            "download_complete": EventType.DOWNLOAD_COMPLETE,
            "download_completed": EventType.DOWNLOAD_COMPLETE,
            "download": EventType.DOWNLOAD_COMPLETE,
            "rename_complete": EventType.RENAME_COMPLETE,
            "rename_completed": EventType.RENAME_COMPLETE,
            "rename": EventType.RENAME_COMPLETE,
            "download_error": EventType.DOWNLOAD_ERROR,
            "download_failed": EventType.DOWNLOAD_ERROR,
            "error": EventType.DOWNLOAD_ERROR,
            "rss_error": EventType.RSS_ERROR,
            "rss_failed": EventType.RSS_ERROR,
        }
        if explicit_lower in mapping:
            return mapping[explicit_lower]

    # 2. 根据字段推断
    has_title = bool(event.title)
    has_season_or_ep = bool(event.season is not None or event.episode is not None)
    has_error = bool(event.error_msg)

    if has_error:
        # 错误消息中包含 "rss" 或 "RSS" → RSS_ERROR
        if "rss" in str(event.error_msg).lower():
            return EventType.RSS_ERROR
        return EventType.DOWNLOAD_ERROR

    if event.file_name and ("rename" in str(raw).lower() or "complete" in str(raw).lower()):
        return EventType.RENAME_COMPLETE

    if event.torrent_name and "start" in str(raw).lower():
        return EventType.DOWNLOAD_START

    if event.file_name:
        return EventType.RENAME_COMPLETE

    if has_title and has_season_or_ep:
        return EventType.NEW_EPISODE

    if has_title:
        return EventType.NEW_EPISODE

    return EventType.UNKNOWN
