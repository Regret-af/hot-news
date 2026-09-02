# -*- coding: utf-8 -*-
"""配置模块：厂商配置与新闻源。

设计原则：
- 密钥只从环境变量读，.env 由 python-dotenv 加载，绝不写死在代码里
- 配置集中一处（模块级缓存），不每个请求都读一遍 .env
"""
import os
from dataclasses import dataclass

from dotenv import load_dotenv

# ---- 常量：新闻源清单----
# 推荐源（免费、国内可达）：
NEWS_SOURCES: list[tuple[str, str]] = [
    ("阮一峰《科技爱好者周刊》", "https://www.ruanyifeng.com/blog/atom.xml"),   # 阮一峰《科技爱好者周刊》
    ("少数派", "https://sspai.com/feed"),                     # 少数派
    ("Solidot", "https://www.solidot.org/index.rss"),          # Solidot
]

# LLM 费率
PRICE_PER_1K_TOKENS = 0.01


@dataclass(frozen=True)     # frozen=True：配置不可变，防误改
class ProviderConfig:
    base_url: str
    model: str
    api_key: str


def get_provider() -> ProviderConfig:
    """从环境变量读厂商配置。"""

    # 加载环境变量
    load_dotenv()

    # 取 API_KEY
    deepseek = os.environ.get("DEEPSEEK_API_KEY")
    zhipu = os.environ.get("ZHIPU_API_KEY")

    if deepseek:
        return ProviderConfig("https://api.deepseek.com", "deepseek-v4-flash", deepseek)
    elif zhipu:
        return ProviderConfig("https://open.bigmodel.cn/api/paas/v4", "glm-4-flash", zhipu)

    # 没有配置 API_KEY，抛出异常
    raise KeyError("未配置 API Key（参考 .env.example）")


def get_price() -> float:
    """返回 PRICE_PER_1K_TOKENS（配置变更时只改一处）"""
    return PRICE_PER_1K_TOKENS
