# -*- coding: utf-8 -*-
"""
层次：
- LLMError：LLM 调用链路的通用失败（重试耗尽 / 不可重试的 4xx / 畸形 JSON 兜底）
- NoNewsError：所有新闻源都失败，无米下锅 -> 路由层翻译成 503
"""


class LLMError(Exception):
    """LLM 调用失败（消息里带原因；重试策略由调用方决定）"""


class NoNewsError(LLMError):
    """所有新闻源都失败——这是业务层自己判断的"没素材"，不是 LLM 的错"""
