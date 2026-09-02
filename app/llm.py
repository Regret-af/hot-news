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
DIGEST_PROMPT_TEMPLATE = """你是一份科技早报的主编。下面是从 {source_count} 个科技资讯源抓到的 {news_count} 条新闻，每条格式为：[来源] 标题(链接: url): 摘要

{news_block}

请输出一份 3 分钟能读完的早报，严格要求：
1. digest：不超过 150 字的总览摘要，口语化、有信息量；
2. items：从上方新闻中挑出最值得关注的 3-5 条，每条给一句 20 字以内的点评（comment 字段）；
3. source 与 url 必须原样使用上方新闻条目方括号和括号里的值，一字不改，禁止编造；
4. 只输出 JSON，格式：
{{"digest": "...", "items": [{{"title": "...", "summary": "...", "comment": "...", "source": "...", "url": "..."}}]}}
"""


def build_prompt(news: list[NewsItem]) -> str:
    """news_block 每行一条：[来源] 标题(链接: url): 摘要（截断 100 字）。"""

    result: str = ""

    # 遍历新闻，组装 news_block
    for info in news:
        result += f"- [{info.source}] {info.title}(链接: {info.url})：{info.summary[:100]}\n"

    # 组装 prompt
    prompt = DIGEST_PROMPT_TEMPLATE.format(
        source_count = len({item.source for item in news}),
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
    report_date = date.today()
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
                raise LLMError(f"HTTP {e.response.status_code}") from e
        except ValueError as e:
            last_exc = e
            logger.warning("第 %s 次重试，错误如下: %s", attempt, "大模型抽风，畸形JSON")
            time.sleep(_backoff_delay(attempt))

    raise LLMError("重试 N 次仍失败") from last_exc


# ---- 流式管线（两段式）----
# 第二段 prompt：基于同一批新闻 + 已生成的 digest，产出要点 JSON
ITEMS_PROMPT_TEMPLATE = """你是一份科技早报的编辑。早报总览摘要已定稿：

{digest}

候选新闻如下：

{news_block}

请从候选新闻中挑出最值得关注的 3-5 条，整理成早报要点。严格要求：
1. 每条包含 title（原标题）、summary（摘要，60 字内）、comment（你的一句点评，20 字内，锐利但有分寸）；
2. source/url 沿用候选新闻的原值，候选里没有的不要编造；
3. digest 固定填入上方定稿摘要
4. 只输出 JSON：
{{"digest": "...", "items": [{{"title": "...", "summary": "...", "comment": "...", "source": "...", "url": "..."}}]}}
"""


def _parse_sse_line(line: str) -> dict | None:
    """ "data: {JSON}" -> dict；"data: [DONE]" / 空行 / 非 data 行 -> None；"""
    if not line.startswith("data: ") or line == "data: [DONE]":
        return None

    try:
        result = json.loads(line[len("data: "):])
        return result
    except Exception as e:
        logger.warning("JSON解析失败，%s", e)
        return None


def _stream_llm_text(prompt: str, temperature: float = 0.3):
    """ 段 1——流式调用，产出 digest 正文。"""
    config = get_provider()

    payload = {
        "model": config.model,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        "stream_options": {"include_usage": True} 
    }

    try:
        with httpx.Client(timeout=60) as client:
            with client.stream(
                "POST",
                f"{config.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {config.api_key}"},
                json=payload
            ) as r:
                r.raise_for_status()

                # 逐行进行数据解析，流式响应
                for line in r.iter_lines():
                    if not line:
                        continue
                    elif line == "data: [DONE]":
                        break

                    # 解析源文本
                    data = _parse_sse_line(line)

                    # 防御式取值返回
                    if data is None:
                        continue

                    content = data.get("choices", [{}])[0].get("delta", {}).get("content", "")
                    if content:
                        yield ("content", content)

                    # 检查 usage 帧
                    if data.get("usage") is not None:
                        yield ("usage", data.get("usage"))
    except httpx.HTTPStatusError as e:
        logger.warning("调用大模型失败: %s", e)
        raise LLMError(f"HTTP {e.response.status_code}") from e
    except httpx.RequestError as e:
        raise LLMError(f"网络错误: {e}")
    

def _generate_items(news: list[NewsItem], digest: str, retries: int = 3) -> tuple[list[ReportItem], dict | None]:
    """ 段 2——非流式 JSON 调用，产出要点列表。"""
    news_block: str = ""
    
    # 遍历新闻，组装 news_block
    for info in news:
        news_block += f"- [{info.source}] {info.title}(链接: {info.url})：{info.summary[:100]}\n"

    prompt = ITEMS_PROMPT_TEMPLATE.format(digest=digest, news_block=news_block)

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
                usage = data.get("usage", {})
                logger.info("本次共消耗token: %d", usage.get("total_tokens", 0))

                report = parse_report_json(data["choices"][0]["message"]["content"])
                
                return report.items, usage
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
                raise LLMError(f"HTTP {e.response.status_code}") from e
        except ValueError as e:
            last_exc = e
            logger.warning("第 %s 次重试，错误如下: %s", attempt, "大模型抽风，畸形JSON")
            time.sleep(_backoff_delay(attempt))
    
    raise LLMError("重试 N 次仍失败") from last_exc

STREAM_DIGEST_PROMPT_TEMPLATE = """你是一份科技早报的主编。下面是 {news_count} 条新闻，每条格式为：[来源] 标题(链接: url): 摘要

{news_block}

请输出一份 3 分钟能读完的早报，严格要求：
1. 不超过 150 字的总览摘要，口语化、有信息量；
2. 直接输出早报信息，不要输出多余文本，如:"好的", "收到"等等
3. 输出纯文本即可
"""

def stream_digest(news: list[NewsItem]):
    """ 完整管线。事件协议"""

    # 构建新闻块
    news_block: str = ""
    for info in news:
        news_block += f"- [{info.source}] {info.title}(链接: {info.url})：{info.summary[:100]}\n"
    
    # 段1：流式生成 digest
    prompt = STREAM_DIGEST_PROMPT_TEMPLATE.format(
        news_count=len(news),
        news_block=news_block
    )
    
    # 收集 digest 并聚合 usage
    digest_parts = []
    usage_agg = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    has_usage = False
    
    for kind, data in _stream_llm_text(prompt=prompt):
        if kind == "content":
            digest_parts.append(data)
            yield ("content", data)  # 透传流式内容
        elif kind == "usage":
            # 聚合 usage
            usage = data
            for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
                if key in usage:
                    usage_agg[key] += usage.get(key, 0)
                    has_usage = True
    
    # 组装完整 digest
    digest = "".join(digest_parts).strip()
    if not digest:
        # 如果流式没拿到内容，抛出错误
        raise LLMError("流式生成 digest 失败：未收到任何内容")
    
    # 段2：非流式生成 items
    items, items_usage = _generate_items(news, digest)
    
    # 聚合段2的 usage
    if items_usage:
        for key in ["prompt_tokens", "completion_tokens", "total_tokens"]:
            if key in items_usage:
                usage_agg[key] += items_usage.get(key, 0)
                has_usage = True
    
    # 组装最终报告
    report = MorningReport(
        report_date=date.today(),
        digest=digest,
        items=items
    )
    
    # 输出 report
    yield ("report", report.model_dump(mode="json"))
    
    # 输出 usage（如果有）
    if has_usage:
        total_tokens = usage_agg.get("total_tokens", 0)
        cost = round(total_tokens / 1000 * get_price(), 8)
        yield ("usage", {"usage": usage_agg, "cost": cost})
