"""
message_sender.py
消息发送模块。

职责：
    将构建好的消息链推送到配置的所有目标（好友/群聊）。
    支持发送失败后的指数退避重试。

作者：yometenma
版本：1.3.0
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, List, Optional

logger = logging.getLogger(__name__)

# AstrBot 标准 MessageType 值
MESSAGE_TYPE_FRIEND = "FriendMessage"
MESSAGE_TYPE_GROUP = "GroupMessage"

# 用户输入的简写 → AstrBot MessageType 映射
_TYPE_MAP = {
    "friend": MESSAGE_TYPE_FRIEND,
    "group": MESSAGE_TYPE_GROUP,
}


@dataclass
class Target:
    """一个推送目标。"""
    target_type: str          # "friend" 或 "group"
    target_id: str            # 会话 ID（QQ 号 / 群号 / Telegram chat_id 等）
    platform_id: str = "aiocqhttp"  # AstrBot 平台标识符


@dataclass
class SendResult:
    """单次发送的结果。"""
    target: Target
    success: bool
    attempts: int = 0
    error_msg: Optional[str] = None


@dataclass
class BatchSendResult:
    """批量发送的汇总结果。"""
    results: List[SendResult] = field(default_factory=list)
    success_count: int = 0
    fail_count: int = 0

    def all_success(self) -> bool:
        return self.fail_count == 0


async def send_to_targets(
    message_chain: list,
    targets: List[Target],
    context: Any,
    max_retries: int = 3,
    retry_delay_seconds: float = 2.0,
) -> BatchSendResult:
    """向所有目标发送消息（并发），支持重试。

    Args:
        message_chain: AstrBot 消息链（Plain、Image 等组件列表）
        targets: 目标列表
        platform_id: 平台 ID（如 "aiocqhttp"）
        context: AstrBot Context 实例
        max_retries: 最大重试次数（默认 3）
        retry_delay_seconds: 重试基础延迟（默认 2 秒，指数增长）

    Returns:
        BatchSendResult 汇总结果
    """
    if not targets:
        logger.warning("[发送] 目标列表为空，跳过发送")
        return BatchSendResult()

    # 并发向所有目标发送
    tasks = [
        _send_to_single_target(
            message_chain, target, context,
            max_retries, retry_delay_seconds,
        )
        for target in targets
    ]
    results = await asyncio.gather(*tasks)

    success = sum(1 for r in results if r.success)
    fail = len(results) - success
    logger.info(f"[发送] 完成: {success} 成功, {fail} 失败")

    return BatchSendResult(
        results=list(results),
        success_count=success,
        fail_count=fail,
    )


async def _send_to_single_target(
    message_chain: list,
    target: Target,
    context: Any,
    max_retries: int,
    base_delay: float,
) -> SendResult:
    """向单个目标发送，带指数退避重试。"""
    msg_type = _TYPE_MAP.get(target.target_type, target.target_type)
    session = f"{target.platform_id}:{msg_type}:{target.target_id}"

    for attempt in range(1, max_retries + 1):
        try:
            await context.send_message(session, message_chain)
            logger.info(
                f"[发送] 成功 → {target.target_type}:{target.target_id}"
            )
            return SendResult(target=target, success=True, attempts=attempt)

        except Exception as e:
            delay = base_delay * (2 ** (attempt - 1))  # 指数退避
            if attempt < max_retries:
                logger.warning(
                    f"[发送] 第 {attempt}/{max_retries} 次失败，"
                    f"{delay:.1f}s 后重试 → {target.target_type}:{target.target_id} | {e}"
                )
                await asyncio.sleep(delay)
            else:
                logger.error(
                    f"[发送] 全部 {max_retries} 次重试失败 → "
                    f"{target.target_type}:{target.target_id} | {e}",
                    exc_info=True,
                )
                return SendResult(
                    target=target,
                    success=False,
                    attempts=attempt,
                    error_msg=str(e),
                )

    # 不应到达，但保险
    return SendResult(
        target=target,
        success=False,
        attempts=max_retries,
        error_msg="未知错误",
    )
