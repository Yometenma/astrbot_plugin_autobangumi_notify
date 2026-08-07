"""
dedup.py
通知去重模块。

职责：
    基于内容指纹 + 时间窗口对通知事件进行去重，防止短时间内同一条通知被重复推送。

实现：
    内存 LRU 缓存，存储 (fingerprint, timestamp)。
    每次 is_duplicate() 调用时：
    1. 清理过期条目
    2. 检查指纹是否存在
    3. 若不存在或已过期 → 不重复，记录并返回 False
    4. 若存在且未过期 → 重复，返回 True

作者：yometenma
版本：1.1.1
"""

import time
import logging

from constants import DEFAULT_MAX_CACHE_SIZE
from event_parser import ParsedEvent

logger = logging.getLogger(__name__)


class DedupCache:
    """基于内存的去重缓存。

    使用指纹 + 时间戳的简单方案，适合单进程 AstrBot 部署。
    """

    def __init__(self, window_seconds: int = 300):
        """
        Args:
            window_seconds: 去重时间窗口（秒）。默认 300 秒（5 分钟）。
        """
        self._window: float = float(window_seconds)
        # {fingerprint: expire_timestamp}
        self._cache: dict[str, float] = {}
        self._max_size: int = DEFAULT_MAX_CACHE_SIZE

    def is_duplicate(self, event: ParsedEvent) -> bool:
        """检查事件是否在去重窗口内已出现过。

        Args:
            event: 解析后的事件

        Returns:
            True 表示重复（应跳过），False 表示新事件（应推送）。
        """
        self._evict_expired()

        fp = event.content_fingerprint()

        if fp in self._cache:
            logger.info(f"[去重] 指纹已存在: {fp[:16]}... → 跳过")
            return True

        self._add(fp)
        return False

    def _add(self, fingerprint: str) -> None:
        """记录新指纹。"""
        self._cache[fingerprint] = time.time() + self._window

        # 防止内存无限增长：超过最大容量时清理过期条目，还不够则放弃最旧的
        if len(self._cache) > self._max_size:
            self._evict_expired()
            if len(self._cache) > self._max_size:
                # 删除最旧的 20% 条目
                sorted_items = sorted(self._cache.items(), key=lambda x: x[1])
                to_remove = max(int(self._max_size * 0.2), 1)
                for fp, _ in sorted_items[:to_remove]:
                    del self._cache[fp]
                logger.warning(
                    f"[去重] 缓存超过限制，已清理 {to_remove} 条旧记录"
                )

    def _evict_expired(self) -> None:
        """清理过期的指纹条目。"""
        now = time.time()
        expired = {fp for fp, expire in self._cache.items() if expire <= now}
        for fp in expired:
            del self._cache[fp]
        if expired:
            logger.debug(f"[去重] 清理 {len(expired)} 条过期记录")

    def clear(self) -> None:
        """清空全部缓存。"""
        self._cache.clear()

    def __len__(self) -> int:
        return len(self._cache)
