"""astrbot_plugin_autobangumi_notify — AutoBangumi Webhook 通知转发插件。"""

from .main import AutoBangumiNotifyPlugin, __version__
from .config import PluginConfig
from .exceptions import (
    AutoBangumiNotifyError,
    ConfigurationError,
    EventParseError,
    LLMRewriteError,
    MessageSendError,
)
from .constants import DEFAULT_TASK_INSTRUCTION
from .event_parser import EventType, ParsedEvent, parse_event, build_notification_text
from .llm_rewriter import rewrite_with_llm
from .message_sender import Target, SendResult, BatchSendResult, send_to_targets
from .dedup import DedupCache

__all__ = [
    "AutoBangumiNotifyPlugin",
    "__version__",
    "PluginConfig",
    "AutoBangumiNotifyError",
    "ConfigurationError",
    "EventParseError",
    "LLMRewriteError",
    "MessageSendError",
    "DEFAULT_TASK_INSTRUCTION",
    "EventType",
    "ParsedEvent",
    "parse_event",
    "build_notification_text",
    "rewrite_with_llm",
    "Target",
    "SendResult",
    "BatchSendResult",
    "send_to_targets",
    "DedupCache",
]
