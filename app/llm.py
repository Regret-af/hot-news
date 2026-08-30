# -*- coding: utf-8 -*-
"""LLM 客户端模块：prompt 构建、结构化摘要、流式输出、重试。

容错分层（本项目两大容错点之二）：
- 网络层错误（超时/断网）-> 指数退避重试
- 429 限流 -> 退避重试（Day 7 周测勘误的正式落地！）
- 4xx 其他（401 key 错等）-> 不重试，直接抛 LLMError
"""
import logging

from app.config import ProviderConfig, get_provider
from app.schemas import MorningReport, NewsItem

logger = logging.getLogger(__name__)

# ---- Prompt 模板（技术亮点：Prompt 模板化——prompt 不散落在代码里，集中成常量）----
DIGEST_PROMPT_TEMPLATE = """你是一份科技早报的主编。下面是从 {source_count} 个科技资讯源抓到的 {news_count} 条新闻：

{news_block}

请输出一份 3 分钟能读完的早报，严格要求：
1. digest：不超过 150 字的总览，口语化、有信息量；
2. items：从上述新闻中挑出最值得关注的 3-5 条，每条给一句 20 字以内的点评（comment 字段）；
3. 只输出 JSON，格式：
{{"digest": "...", "items": [{{"title": "...", "summary": "...", "comment": "..."}}]}}
"""


def build_prompt(news: list[NewsItem]) -> str:
    """TODO Day 12: 按 DIGEST_PROMPT_TEMPLATE 填充，news_block 每行一条 '- 标题：摘要'。"""
    raise NotImplementedError


def parse_report_json(text: str) -> MorningReport:
    """TODO Day 12: LLM 返回的 JSON 字符串 -> MorningReport（json.loads + model_validate；
    注意 LLM 有概率输出 ```json 包裹，要剥掉再解析——容错点）。"""
    raise NotImplementedError


def chat_digest(news: list[NewsItem], retries: int = 3) -> MorningReport:
    """TODO Day 12: 非流式获取早报。
    - 构造 chat/completions 请求（可研究 response_format={"type": "json_object"} 提升结构化率）
    - 重试分层：TimeoutException/ConnectError/429 -> time.sleep(0.5 * 2**(attempt-1)) 后重试；
      其他 4xx -> 直接 raise LLMError（Day 6 retry_call 的项目化版本，记得 prompt 透传）
    - 成功后 parse_report_json 返回
    """
    raise NotImplementedError


def stream_digest(news: list[NewsItem]):
    """TODO Day 13: 流式版生成器——yield ("content", 增量文本)，参考你 Day 10 的
    stream_chat（注意按项目规范重写：类型化事件、logging、429 处理）。"""
    raise NotImplementedError
