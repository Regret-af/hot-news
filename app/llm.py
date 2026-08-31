# -*- coding: utf-8 -*-
"""LLM 客户端模块：prompt 构建、结构化摘要、流式输出、分层重试。

容错分层（本项目两大容错点之二）：
- 网络层错误（超时/断网）-> 指数退避重试
- 429 限流 -> 退避重试（Day 7 周测勘误的正式落地！）
- 其他 4xx（401 key 错等）-> 不重试，直接抛 LLMError
- 畸形 JSON -> ValueError -> 视为模型抽风，计入重试
"""
import logging

import httpx

from app.config import get_price, get_provider
from app.errors import LLMError
from app.schemas import MorningReport, NewsItem

logger = logging.getLogger(__name__)

# ---- Prompt 模板（技术亮点：Prompt 模板化）----
# 注意：模板里必须出现"JSON"字样——DeepSeek 的 json_object 模式要求 prompt 含该词
DIGEST_PROMPT_TEMPLATE = """你是一份科技早报的主编。下面是从 {source_count} 个科技资讯源抓到的 {news_count} 条新闻：

{news_block}

请输出一份 3 分钟能读完的早报，严格要求：
1. digest：不超过 150 字的总览摘要，口语化、有信息量；
2. items：挑出最值得关注的 3-5 条，每条给一句 20 字以内的点评（comment 字段），source/url 沿用原新闻；
3. 只输出 JSON，格式：
{{"digest": "...", "items": [{{"title": "...", "summary": "...", "comment": "...", "source": "...", "url": "..."}}]}}
"""


def build_prompt(news: list[NewsItem]) -> str:
    """TODO Day 12: 按 DIGEST_PROMPT_TEMPLATE 填充。
    news_block 每行一条 '- 标题：摘要'（summary 截断到 100 字，控制 token）。"""
    raise NotImplementedError


def _backoff_delay(attempt: int) -> float:
    """指数退避秒数：第 1 次重试等 0.5s，之后翻倍。纯函数——好测（Day 12 测试覆盖）。

    TODO Day 12: 一行实现。"""
    raise NotImplementedError


def parse_report_json(text: str) -> MorningReport:
    """TODO Day 12: LLM 返回的 JSON 字符串 -> MorningReport。
    容错：LLM 有概率用 ```json ... ``` 包裹（哪怕 json_object 模式）——先剥壳再 json.loads；
    解析失败 raise ValueError（chat_digest 会把它当可重试错误）。"""
    raise NotImplementedError


def chat_digest(news: list[NewsItem], retries: int = 3) -> MorningReport:
    """TODO Day 12: 非流式获取早报（/news 接口的引擎）。
    流程：
    1. prompt = build_prompt(news)；payload 带 response_format={"type": "json_object"}
    2. 重试循环（结构参考你 Day 6 的 retry_call，但分层策略升级）：
       - TimeoutException / ConnectError -> 可重试
       - HTTPStatusError 且 status_code == 429 -> 可重试（限流是暂时的！）
       - HTTPStatusError 其他 4xx/5xx -> raise LLMError（不可重试）
       - ValueError（parse_report_json 抛的畸形 JSON）-> 可重试（模型抽风）
       - 可重试：last_exc 记录，attempt < retries 时 time.sleep(_backoff_delay(attempt))
    3. 重试耗尽 raise LLMError("重试 N 次仍失败") from last_exc
    提示：raise_for_status() 要在 stream 之外正常用；usage 在响应 JSON 的 "usage" 字段，
    logger.info 记录每次调用的 token 消耗。"""
    raise NotImplementedError


def stream_digest(news: list[NewsItem]):
    """TODO Day 13: 流式管线（两段式，原因见 day12.md 第 4 节）：
    yield ("phase", "generating") -> yield ("content", 增量)×N
    -> 第二段调用产出 items -> yield ("report", MorningReport) -> yield ("usage", {...}, cost)
    类型化元组事件（Day 10 批改的教训：禁止混合类型 yield）。"""
    raise NotImplementedError
