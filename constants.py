"""
constants.py
插件全局常量定义。

集中管理所有魔法字符串和默认值，方便维护和避免散落各处。

作者：yometenma
版本：1.3.0
"""

# ---- 事件类型标记 ----
# 在 event_parser 中用于匹配显式字段的关键词映射
EVENT_TYPE_KEY_NEW_EPISODE = "new_episode"
EVENT_TYPE_KEY_DOWNLOAD_START = "download_start"
EVENT_TYPE_KEY_DOWNLOAD_COMPLETE = "download_complete"
EVENT_TYPE_KEY_RENAME_COMPLETE = "rename_complete"
EVENT_TYPE_KEY_DOWNLOAD_ERROR = "download_error"
EVENT_TYPE_KEY_RSS_ERROR = "rss_error"
EVENT_TYPE_KEY_UNKNOWN = "unknown"

# ---- 默认配置值 ----
DEFAULT_PLATFORM_ID = "aiocqhttp"
DEFAULT_WEBHOOK_PATH = "/api/autobangumi/notify"
DEFAULT_USE_LLM = True
DEFAULT_ENABLE_DEDUP = True
DEFAULT_DEDUP_WINDOW_SECONDS = 300
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 2.0
DEFAULT_MAX_CACHE_SIZE = 500

# ---- LLM ----
DEFAULT_TASK_INSTRUCTION = (
    "请用你的口吻简要转述以下 AutoBangumi 通知。"
    "保持信息准确，语气自然。"
)

# ---- 消息发送 ----
MESSAGE_SESSION_TEMPLATE = "{platform_id}:{target_type}:{target_id}"

# ---- 去重 ----
DEDUP_FINGERPRINT_HASH = "sha256"

# ---- 重试 ----
RETRY_BACKOFF_BASE = 2.0  # 指数退避基数
