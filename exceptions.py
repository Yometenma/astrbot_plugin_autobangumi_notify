"""
exceptions.py
AutoBangumi 通知插件自定义异常层级。

参照 AstrBot 成熟插件的模式，定义从基类派生的异常树，
让调用方能按语义捕获特定异常类型，而不是笼统地用 except Exception。

作者：yometenma
版本：1.3.0
"""


class AutoBangumiNotifyError(Exception):
    """插件所有异常的基类。"""


class ConfigurationError(AutoBangumiNotifyError):
    """配置相关错误——缺失必填字段、格式非法等。"""


class EventParseError(AutoBangumiNotifyError):
    """Webhook 事件解析失败——JSON 格式异常、字段缺失等。"""


class LLMRewriteError(AutoBangumiNotifyError):
    """LLM 转述失败——Provider 不可用、调用超时、返回格式异常等。"""


class MessageSendError(AutoBangumiNotifyError):
    """消息发送失败——平台不可达、目标不存在、发送超时等。"""
