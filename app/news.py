# -*- coding: utf-8 -*-
"""新闻取数模块：RSS/Atom 拉取与解析。

容错分层：
- 单个源失败（超时/解析错误）只损失该源，不拖垮整份早报 -> 记 warning 日志后跳过
"""
import logging
import feedparser

from app.config import NEWS_SOURCES
from app.schemas import NewsItem

logger = logging.getLogger(__name__)

FEED_TIMEOUT = 10.0        # 新闻源超时要短——它挂了不该拖慢用户


def fetch_feed(url: str) -> list[NewsItem]:
    """抓取并解析单个 RSS/Atom 源，返回最新 NewsItem 列表。"""
    d = feedparser.parse(url)

    result: list[NewsItem] = []

    for entry in d.entries[:5]:
        title = entry.get("title", "")
        summary = entry.get("summary")
        link = entry.get("link")

        if title == "":
            continue

        result.append(
            NewsItem(
                title=title,
                summary=summary,
                source=next((n for n, u in NEWS_SOURCES if u == url), "未知来源"),
                url=link
                ))

    return result


def fetch_all(sources: list[str] | None = None) -> list[NewsItem]:
    """抓取全部源，单源失败跳过（warning 日志），永不抛出。"""
    # 判断是否传入数据源，未传入使用默认数据源
    if sources is None:
        sources = [source[1] for source in NEWS_SOURCES]

    result: list[NewsItem] = []

    # 遍历数据源，进行新闻抓取
    for source in sources:
        try:
            result.extend(fetch_feed(source))
        except Exception as e:
            logger.warning("源 %s 失败: %s", source, e)
            continue
    
    return result
