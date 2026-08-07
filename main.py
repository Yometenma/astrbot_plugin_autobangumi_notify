"""
astrbot_plugin_autobangumi_notify
AutoBangumi 通知转发插件

功能：
    接收 AutoBangumi 的 Webhook 通知，通过 AstrBot 的 LLM
    以机器人自身人格转述后推送到指定会话（好友/群聊）。

特性：
    - 多事件类型识别（新番更新 / 下载 / 重命名 / 错误）
    - 多目标推送（好友 + 群聊自由组合）
    - 内容去重（指纹 + 时间窗口）
    - 发送失败重试（指数退避）
    - LLM 以机器人自身人格转述（不绑定固定人设）
    - 向后兼容旧版配置（target_qq 自动迁移）

作者：yometenma
版本：1.1.1
"""

import json

from astrbot.api.message_components import Plain, Image
from astrbot.api.star import Context, Star, register

from .config import PluginConfig
from .event_parser import ParsedEvent, parse_event, build_notification_text
from .exceptions import ConfigurationError, EventParseError
from .llm_rewriter import rewrite_with_llm
from .message_sender import Target, send_to_targets
from .dedup import DedupCache

__version__ = "1.1.2"


@register(
    "astrbot_plugin_autobangumi_notify",
    "yometenma",
    "AutoBangumi 通知转发",
    __version__,
)
class AutoBangumiNotifyPlugin(Star):
    """AutoBangumi 通知转发插件。"""

    def __init__(self, context: Context, config: dict):
        super().__init__(context)
        self.cfg = PluginConfig(config)  # 已验证的配置对象

        # ---- 推送目标（兼容旧 target_qq） ----
        self.targets: list[Target] = self._build_targets()

        # ---- 延迟初始化的组件 ----
        self.dedup_cache: DedupCache | None = None

    async def initialize(self) -> None:
        """插件加载完成后的初始化。"""
        if self.cfg.enable_dedup:
            self.dedup_cache = DedupCache(
                window_seconds=self.cfg.dedup_window_seconds,
            )

        self.context.register_web_api(
            self.cfg.webhook_path,
            self._handle_webhook,
            ["POST"],
            "AutoBangumi 通知接收 Webhook",
        )

        self.cfg.log_summary()
        self.logger.info(f"插件 v{__version__} 已就绪")

    async def terminate(self) -> None:
        """插件卸载时清理资源。"""
        if self.dedup_cache:
            self.dedup_cache.clear()
        self.logger.info("插件已卸载")

    # ==================== 目标解析 ====================

    def _build_targets(self) -> list[Target]:
        """从已校验的配置构建 Target 列表，兼容旧版 target_qq。"""
        targets = [
            Target(target_type=t["type"], target_id=t["id"])
            for t in self.cfg.targets
        ]
        if not targets and self.cfg.legacy_target_qq:
            self.logger.info(
                f"检测到旧版 target_qq={self.cfg.legacy_target_qq}，"
                "已自动迁移到 targets"
            )
            targets.append(Target(
                target_type="friend",
                target_id=self.cfg.legacy_target_qq,
            ))
        return targets

    # ==================== Webhook 处理 ====================

    async def _handle_webhook(self, request):
        """接收 AutoBangumi 的 Webhook POST 请求。"""
        try:
            raw = await request.json()
            self.logger.info(
                "收到 Webhook: "
                f"{json.dumps(raw, ensure_ascii=False, default=str)[:300]}"
            )

            # 1. 解析事件
            event = parse_event(raw)
            self.logger.info(
                f"识别事件: {event.event_type.value} "
                f"| {event.title or '未知番剧'}"
            )

            # 2. 去重
            if self.dedup_cache and self.dedup_cache.is_duplicate(event):
                return {"status": "ok", "message": "duplicate"}

            # 3. 构建摘要
            plain_text = build_notification_text(event)
            if not plain_text:
                self.logger.warning("通知内容为空，忽略")
                return {"status": "ok", "message": "ignored"}

            # 4. 分发
            await self._dispatch(event, plain_text)
            return {"status": "ok", "message": "received"}

        except EventParseError as e:
            self.logger.error(f"事件解析失败: {e}")
            return {"status": "error", "message": str(e)}
        except Exception as e:
            self.logger.error(f"Webhook 处理异常: {e}", exc_info=True)
            return {"status": "error", "message": str(e)}

    # ==================== 消息分发 ====================

    async def _dispatch(self, event: ParsedEvent, plain_text: str):
        """构建消息链并分发到所有目标。"""
        if not self.targets:
            self.logger.error("未配置推送目标，无法发送")
            raise ConfigurationError("未配置推送目标")

        message_chain = []

        # 文本
        if self.cfg.use_llm:
            provider = self.context.get_using_provider()
            llm_text = await rewrite_with_llm(
                text=plain_text,
                provider=provider,
                task_instruction=self.cfg.llm_task_instruction,
            )
            message_chain.append(Plain(llm_text))
        else:
            message_chain.append(Plain(f"[AutoBangumi] {plain_text}"))

        # 海报图
        poster = event.poster_url or event.raw.get("poster")
        if poster:
            try:
                message_chain.append(Image.fromURL(poster))
            except Exception as e:
                self.logger.warning(f"加载海报失败: {e}")

        # 发送
        result = await send_to_targets(
            message_chain=message_chain,
            targets=self.targets,
            platform_id=self.cfg.platform_id,
            context=self.context,
            max_retries=self.cfg.max_retries,
            retry_delay_seconds=self.cfg.retry_delay_seconds,
        )

        if not result.all_success():
            failed = [r.target for r in result.results if not r.success]
            self.logger.warning(
                "部分目标发送失败: "
                f"{[f'{t.target_type}:{t.target_id}' for t in failed]}"
            )
