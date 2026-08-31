# -*- coding: utf-8 -*-
"""FastAPI 入口：路由层。业务在 news.py/llm.py，路由只做参数校验和异常翻译（Day 8 的分层）。"""
import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import StreamingResponse

from app.config import get_provider
from app.errors import LLMError, NoNewsError
from app.llm import chat_digest, stream_digest
from app.news import fetch_all
from app.schemas import MorningReport

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="热点早报生成器", description="阶段 0 热身项目 A")


def get_report_provider():
    """依赖工厂：返回"生成一份早报"的函数。

    这里串起完整业务链：抓新闻 -> 调 LLM -> 结构化早报。
    业务异常（NoNewsError/LLMError）向上抛，由路由层翻译成 HTTP 状态码——
    异常翻译只在路由层做一次，业务模块保持"纯业务"。
    """
    def provide() -> MorningReport:
        news = fetch_all()
        if not news:
            raise NoNewsError("所有新闻源都失败了")
        return chat_digest(news)
    return provide


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/provider")
def provider_info() -> dict:
    config = get_provider()
    return {
        "base_url": config.base_url,
        "model": config.model
    }


@app.get("/news")
def get_news(report_provider=Depends(get_report_provider)) -> MorningReport:
    try:
        return report_provider()
    except NoNewsError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except LLMError as e:
        logger.exception("LLM 链路失败")
        raise HTTPException(status_code=502, detail=f"LLM 链路失败: {e}") from e

@app.get("/news/stream")
def get_news_stream() -> StreamingResponse:
    # TODO Day 13: SSE——帧序见 docs/frontend-brief.md 3.3：
    # {"phase":"fetching_news"} -> {"phase":"generating"} -> {"content":增量}×N
    # -> {"report":{...}} -> {"usage":{...},"cost":...}（可缺席）-> [DONE]
    # 错误任何时刻走 {"error": ...} 帧。前端 api.js 已按此实现（frame.error 优先分发）。
    raise NotImplementedError
