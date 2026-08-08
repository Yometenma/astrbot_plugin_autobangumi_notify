"""
llm_rewriter.py
LLM 转述模块。

职责：
    调用 AstrBot 的 LLM Provider，让机器人用自己的口吻转述通知文本。

设计原则：
    插件不定义机器人人格——人格由 AstrBot 自身的配置决定。
    这里只传入「任务指令」告诉 LLM 要做什么，不定义它是谁。

作者：yometenma
版本：1.3.0
"""

import logging
from typing import Any, Optional

from .constants import DEFAULT_TASK_INSTRUCTION

logger = logging.getLogger(__name__)


async def rewrite_with_llm(
    text: str,
    provider: Any,
    task_instruction: Optional[str] = None,
) -> str:
    """调用 LLM 转述通知文本。

    Args:
        text: 原始通知摘要文本
        provider: AstrBot LLM Provider 实例
        task_instruction: 可选的任务指令。
            若不传，LLM 会以 AstrBot 自身人格自由转述；
            若传入，LLM 会在此指令约束下转述（仍保留自身人格）。

    Returns:
        转述后的文本；如果 LLM 不可用或调用失败，返回原文。
    """
    if provider is None:
        logger.warning("[LLM] 无可用 Provider，使用原文")
        return text

    system_prompt = task_instruction or DEFAULT_TASK_INSTRUCTION

    try:
        resp = await provider.text_chat(
            prompt=text,
            system_prompt=system_prompt,
        )
        if resp and resp.result_chain:
            plain = resp.result_chain.get_plain_text()
            if plain:
                logger.debug(f"[LLM] 转述成功: {plain[:100]}...")
                return plain
        logger.warning("[LLM] 返回结果为空，使用原文")
        return text
    except Exception as e:
        logger.error(f"[LLM] 转述失败，使用原文: {e}", exc_info=True)
        return text
