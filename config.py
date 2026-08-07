"""
config.py
插件配置模型与校验。

使用 Pydantic 对 AstrBot 传入的原始 dict 配置做类型校验和默认值填充，
让 main.py 拿到的是已经过验证的可靠配置对象。

作者：yometenma
版本：1.1.1
"""

from typing import Optional

from astrbot.api import logger

from .constants import (
    DEFAULT_PLATFORM_ID,
    DEFAULT_WEBHOOK_PATH,
    DEFAULT_USE_LLM,
    DEFAULT_ENABLE_DEDUP,
    DEFAULT_DEDUP_WINDOW_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_RETRY_DELAY_SECONDS,
)


class PluginConfig:
    """插件配置容器——从 raw dict 解析并校验后的配置对象。

    之所以不用 Pydantic BaseModel（不像 self_learning 那样复杂），
    是因为我们的配置项较少，手写解析足够清晰且不引入额外依赖。
    """

    def __init__(self, raw: dict):
        # ---- 基础配置 ----
        self.platform_id: str = str(
            raw.get("platform_id", DEFAULT_PLATFORM_ID)
        )
        self.use_llm: bool = _parse_bool(raw, "use_llm", DEFAULT_USE_LLM)
        self.webhook_path: str = str(
            raw.get("webhook_path", DEFAULT_WEBHOOK_PATH)
        )

        # ---- LLM 转述指令 ----
        task = str(raw.get("llm_system_prompt", "")).strip()
        self.llm_task_instruction: Optional[str] = task or None

        # ---- 去重 ----
        self.enable_dedup: bool = _parse_bool(
            raw, "enable_dedup", DEFAULT_ENABLE_DEDUP
        )
        self.dedup_window_seconds: int = _parse_int(
            raw, "dedup_window_seconds", DEFAULT_DEDUP_WINDOW_SECONDS
        )

        # ---- 重试 ----
        self.max_retries: int = _parse_int(
            raw, "max_retries", DEFAULT_MAX_RETRIES
        )
        self.retry_delay_seconds: float = _parse_float(
            raw, "retry_delay_seconds", DEFAULT_RETRY_DELAY_SECONDS
        )

        # ---- 推送目标 ----
        self.targets: list[dict] = self._parse_targets(raw)


    @staticmethod
    def _parse_targets(raw: dict) -> list[dict]:
        """解析新版 targets 配置。"""
        items = raw.get("targets")
        if not isinstance(items, list):
            return []
        result = []
        for item in items:
            if isinstance(item, dict):
                t_type = str(item.get("type", "friend"))
                t_id = str(item.get("id", ""))
                if t_id:
                    result.append({
                        "type": t_type,
                        "id": t_id,
                        "platform": item.get("platform"),
                    })
        return result

    def log_summary(self) -> None:
        """打印配置摘要日志。"""
        targets_desc = ", ".join(
            f"{t['type']}:{t['id']}" for t in self.targets
        ) if self.targets else "无（请配置 targets）"
        logger.info(
            "配置摘要 | "
            f"platform={self.platform_id} | "
            f"webhook={self.webhook_path} | "
            f"LLM={'开' if self.use_llm else '关'} | "
            f"去重={'开' if self.enable_dedup else '关'}"
            f"({self.dedup_window_seconds}s) | "
            f"重试={self.max_retries}次 | "
            f"目标={targets_desc}"
        )


def _parse_bool(raw: dict, key: str, default: bool) -> bool:
    """安全解析布尔值。"""
    value = raw.get(key, default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes", "on")
    return bool(value)


def _parse_int(raw: dict, key: str, default: int) -> int:
    """安全解析整数。"""
    try:
        return int(raw.get(key, default))
    except (TypeError, ValueError):
        return default


def _parse_float(raw: dict, key: str, default: float) -> float:
    """安全解析浮点数。"""
    try:
        return float(raw.get(key, default))
    except (TypeError, ValueError):
        return default
