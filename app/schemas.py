# -*- coding: utf-8 -*-
"""数据模型：全项目的 pydantic 模型只定义一次，处处导入（Day 8 批改的教训）。

契约来源：docs/frontend-brief.md 第 3 节（唯一契约）。
两个"条目"模型是不同的东西，不要合并：
- NewsItem：RSS 抓到的原始新闻（喂给 LLM 的原料）
- ReportItem：早报要点（LLM 产出，带 AI 点评 comment）
"""
from datetime import date

from pydantic import BaseModel, Field


class NewsItem(BaseModel):
    """一条原始新闻（从 RSS 条目提取，作为 LLM 的输入材料）"""
    title: str = Field(min_length=1)
    summary: str = ""
    source: str          # 源名称（如 "少数派"），不是 URL
    url: str = ""


class ReportItem(BaseModel):
    """早报要点（LLM 产出；契约 3.2：source/url 可能缺失，前端容忍 null）"""
    title: str = Field(min_length=1)
    summary: str = ""
    comment: str = Field(default="", description="AI 一句话点评")
    source: str | None = None
    url: str | None = None


class MorningReport(BaseModel):
    """一份结构化早报（/news 的响应体；report 帧的 report 字段）"""
    report_date: date
    digest: str = Field(description="AI 生成的 3 分钟速览摘要")
    items: list[ReportItem] = Field(default=[], description="3–5 条由 prompt 约束，模型层不做强校验避免误伤重试")
