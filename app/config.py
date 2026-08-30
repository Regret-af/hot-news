# -*- coding: utf-8 -*-
"""配置模块：厂商配置与新闻源。

设计原则（对照你 Day 6 的 provider()，按项目规范重写）：
- 密钥只从环境变量读，.env 由 python-dotenv 加载，绝不写死在代码里
- 配置集中一处（模块级缓存），不每个请求都读一遍 .env
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# ---- 常量：新闻源清单（Day 12 可自行增删；feedparser 能解析 RSS/Atom）----
# 推荐源（免费、国内可达）：
NEWS_SOURCES: list[str] = [
    "https://www.ruanyifeng.com/blog/atom.xml",   # 阮一峰《科技爱好者周刊》
    "https://sspai.com/feed",                     # 少数派
    "https://www.solidot.org/index.rss",          # Solidot
]

# LLM 费率（简化版，元/千 token），README 里注明是简化假设
PRICE_PER_1K_TOKENS = 0.001


@dataclass(frozen=True)     # frozen=True：配置不可变，防误改（Day 4 dataclass 进阶）
class ProviderConfig:
    base_url: str
    model: str
    api_key: str


def get_provider() -> ProviderConfig:
    """从环境变量读厂商配置。

    规则与 Day 6 一致：DEEPSEEK_API_KEY 优先，其次 ZHIPU_API_KEY，
    都没有 -> raise KeyError("未配置 API Key（参考 .env.example）")。
    TODO Day 12: 实现（注意返回 ProviderConfig 而不是三元组——dataclass 比裸元组可读）。
    """
    raise NotImplementedError


def get_price() -> float:
    """TODO Day 12: 返回 PRICE_PER_1K_TOKENS（一行；为什么要包一层？配置变更时只改一处）"""
    raise NotImplementedError
