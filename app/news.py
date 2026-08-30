# -*- coding: utf-8 -*-
"""新闻取数模块：RSS/Atom 拉取与解析。

容错分层（本项目两大容错点之一，另一个在 llm.py）：
- 单个源失败（超时/解析错误）只损失该源，不拖垮整份早报 -> 记 warning 日志后跳过
"""
import logging

from app.config import NEWS_SOURCES
from app.schemas import NewsItem

logger = logging.getLogger(__name__)

FEED_TIMEOUT = 10.0        # 新闻源超时要短——它挂了不该拖慢用户


def fetch_feed(url: str) -> list[NewsItem]:
    """抓取并解析单个 RSS/Atom 源，返回最新 NewsItem 列表。

    TODO Day 12:
    - feedparser.parse(url) 拿 d.entries（feedparser 自带请求；拿不到再考虑 httpx 下载后喂 parse）
    - 每条 entry 提取 title / summary / link，source 填本源名称（给 NEWS_SOURCES 配 (名称, url) 元组更佳）
    - 只取前 5 条（早报不贪多）
    - 任何异常向上抛（跳过策略在 fetch_all 里做，本函数只管单个源）
    """
    raise NotImplementedError


def fetch_all(sources: list[str] | None = None) -> list[NewsItem]:
    """抓取全部源，单源失败跳过（warning 日志），永不抛出。

    TODO Day 12:
    - 遍历 sources（默认 NEWS_SOURCES），try/except 包住 fetch_feed
    - 失败：logger.warning("源 %s 失败: %s", url, e) 后 continue
    - 成功：extend 进结果列表
    - 返回合并列表（不超过 10 条，给 LLM 的 prompt 别太长）
    """
    raise NotImplementedError
