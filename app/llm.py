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
import json
import time

from datetime import date

from app.config import get_price, get_provider
from app.errors import LLMError
from app.schemas import MorningReport, NewsItem, ReportItem

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
    """news_block 每行一条 '- 标题：摘要'（summary 截断到 100 字，控制 token）。"""

    result: str = ""

    # 遍历新闻，组装 news_block
    for info in news:
        result += f"- {info.title}：{info.summary[:100]}\n"

    # 组装 prompt
    prompt = DIGEST_PROMPT_TEMPLATE.format(
        source_count = 3,
        news_count = len(news),
        news_block = result
    )

    return prompt


def _backoff_delay(attempt: int) -> float:
    """指数退避秒数：第 1 次重试等 0.5s，之后翻倍。"""
    return 0.5 * 2 ** (attempt - 1)


def parse_report_json(text: str) -> MorningReport:
    """容错：LLM 有概率用 ```json ... ``` 包裹（哪怕 json_object 模式）——先剥壳再 json.loads；
    解析失败 raise ValueError（chat_digest 会把它当可重试错误）。"""
    # 进行简单的容错
    text = text.strip().removeprefix("```json").removesuffix("```")

    # 进行解析
    try:
        data = json.loads(text)
    except Exception as e:
        logger.warning("解析返回数据出错 %s", e)
        raise ValueError(f"JSON解析失败: {e}") from e

    if "digest" not in data:
        raise ValueError("缺少必填字段: digest")
    if "items" not in data or not isinstance(data["items"], list):
        raise ValueError("缺少必填字段: items 或 items 不是列表")

    # 进行本地化
    report_date = date.today().isoformat()
    digest = data.get("digest", "...")

    result_items = []
    for items in data.get("items", []):
        title = items.get("title")
        summary = items.get("summary")
        comment = items.get("comment")
        source = items.get("source")
        url = items.get("url")

        result_items.append(
            ReportItem(title=title, summary=summary, comment=comment, source=source, url=url
        ))

    result = MorningReport(report_date=report_date, digest=digest, items=result_items)
    
    return result


def chat_digest(news: list[NewsItem], retries: int = 3) -> MorningReport:
    """流程：
    1. prompt = build_prompt(news)；payload 带 response_format={"type": "json_object"}
    2. 重试循环：
       - TimeoutException / ConnectError -> 可重试
       - HTTPStatusError 且 status_code == 429 -> 可重试（限流是暂时的！）
       - HTTPStatusError 其他 4xx/5xx -> raise LLMError（不可重试）
       - ValueError（parse_report_json 抛的畸形 JSON）-> 可重试（模型抽风）
       - 可重试：last_exc 记录，attempt < retries 时 time.sleep(_backoff_delay(attempt))
    3. 重试耗尽 raise LLMError("重试 N 次仍失败") from last_exc
    提示：raise_for_status() 要在 stream 之外正常用；logger.info 记录每次调用的 token 消耗。"""
    # 获取 prompt
    prompt = build_prompt(news)

    # 调用大模型，出错根据策略进行指数级退避重试
    for attempt in range(1, retries + 1):
        try:
            config = get_provider()

            # 构建请求参数
            payload = {
                "model": config.model,
                "temperature": 0.7,
                "messages": [{"role": "user", "content": prompt}],
                "response_format": {"type": "json_object"}
            }
            # 调用大模型
            with httpx.Client(timeout=30) as client:
                response = client.post(
                    url=f"{config.base_url}/chat/completions",
                    headers={"Authorization": f"Bearer {config.api_key}"},
                    json=payload
                )
                response.raise_for_status()

                data = response.json()
                logger.info("本次消耗token: %d", data.get("usage", {}).get("total_tokens", 0))

                return parse_report_json(data["choices"][0]["message"]["content"])
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            last_exc = e
            logger.warning("第 %s 次重试，错误如下: %s", attempt, e)
            time.sleep(_backoff_delay(attempt))
        except httpx.HTTPStatusError as e:
            last_exc = e
            if e.response.status_code == 429:
                logger.warning("第 %s 次重试，错误如下: %s", attempt, e)
                time.sleep(_backoff_delay(attempt))
            else:
                logger.warning("调用大模型失败: %s", e)
                raise LLMError() from e
        except ValueError as e:
            last_exc = e
            logger.warning("第 %s 次重试，错误如下: %s", attempt, "大模型抽风，畸形JSON")
            time.sleep(_backoff_delay(attempt))

    raise LLMError("重试 N 次仍失败") from last_exc


def stream_digest(news: list[NewsItem]):
    """TODO Day 13: 流式管线（两段式，原因见 day12.md 第 4 节）：
    yield ("phase", "generating") -> yield ("content", 增量)×N
    -> 第二段调用产出 items -> yield ("report", MorningReport) -> yield ("usage", {...}, cost)
    类型化元组事件（Day 10 批改的教训：禁止混合类型 yield）。"""
    
    raise NotImplementedError
