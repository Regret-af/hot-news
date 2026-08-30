# -*- coding: utf-8 -*-
"""FastAPI 入口：路由层。业务在 news.py/llm.py，路由只做参数校验和异常翻译（Day 8 的分层）。"""
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_provider
from app.llm import chat_digest, stream_digest
from app.news import fetch_all
from app.schemas import MorningReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="热点早报生成器", description="阶段 0 热身项目 A")


def get_report_provider():
    """依赖工厂：返回"生成一份早报"的函数（Day 9 的 DI 模式，测试可 override）。"""
    def provide() -> MorningReport:
        news = fetch_all()
        if not news:
            raise LLMErrorNoNews("所有新闻源都失败了")
        return chat_digest(news)
    return provide


class LLMErrorNoNews(Exception):
    """TODO Day 12: 想想这个异常放哪定义更合适（提示：schemas.py 或单独 errors.py）"""


@app.get("/health")
def health() -> dict:
    # TODO Day 12: 返回 {"status": "ok"}（部署标配）
    raise NotImplementedError


@app.get("/news")
def get_news(report_provider=Depends(get_report_provider)) -> MorningReport:
    # TODO Day 12:
    # - 业务异常翻译：无新闻可用 -> HTTPException(503, ...)（服务端暂时没有内容）
    # - 其余异常 500 由 FastAPI 兜底，但 logger.exception 记录堆栈
    raise NotImplementedError


@app.get("/news/stream")
def get_news_stream() -> StreamingResponse:
    # TODO Day 13: SSE 打字机——流式吐 digest 正文，帧协议沿用你 Day 10 的约定
    # （{"content": ...} 增量帧 / {"error": ...} 错误帧 / data: [DONE]）
    raise NotImplementedError


@app.get("/provider")
def provider_info() -> dict:
    """TODO Day 12: 返回当前厂商配置（base_url 和 model，绝不返回 api_key！）——文档/调试用。"""
    raise NotImplementedError
