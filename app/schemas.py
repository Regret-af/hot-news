# -*- coding: utf-8 -*-
"""数据模型：全项目的 pydantic/dataclass 模型只定义一次，处处导入（Day 8 批改的教训）。"""
from datetime import date

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """一条新闻（从 RSS 条目提取）"""
    title: str = Field(min_length=1)
    summary: str = ""
    source: str          # 源名称（如 "少数派"），不是 URL
    url: str = ""


class MorningReport(BaseModel):
    """一份结构化早报（LLM JSON mode 的解析目标，Day 12 实现）"""
    report_date: date
    items: list[NewsItem]
    digest: str = Field(description="AI 生成的 3 分钟速览摘要")


class StreamEvent(BaseModel):
    """SSE 帧的事件模型（Day 13 用；沿用你 Day 10 的帧协议思想）"""
    type: str = Field(description="content / usage / error")
    data: str = ""
