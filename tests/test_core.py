# -*- coding: utf-8 -*-
"""
运行（项目根目录）：uv run pytest tests/test_core.py -v
前置：uv add --dev pytest
"""
import json
import os
from datetime import date

import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import ProviderConfig, get_price, get_provider
from app.errors import LLMError, NoNewsError
from app.llm import _backoff_delay, build_prompt, parse_report_json
from app.news import fetch_all
from app.schemas import MorningReport, NewsItem
from app.main import app

client = TestClient(app)


def _sample_news() -> list[NewsItem]:
    return [
        NewsItem(title="AI 编程助手进入团队协作", summary="评审轮次明显减少", source="少数派", url="https://a/1"),
        NewsItem(title="开源推理框架发布新版本", summary="长文本吞吐翻倍", source="爱范儿", url="https://a/2"),
        NewsItem(title="中端机型配置策略生变", summary="存储组合下放到 2000 元档", source="Solidot", url="https://a/3"),
    ]


# ---------- config ----------
@pytest.mark.skipif(
        not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ZHIPU_API_KEY")),
        reason="需要真实 API Key 的冒烟测试，CI 无密钥环境自动跳过"
)
def test_get_provider():
    cfg = get_provider()
    assert isinstance(cfg, ProviderConfig)
    assert cfg.base_url.startswith("https://")
    assert cfg.model and cfg.api_key, "确认 .env 已配置 key"
    assert get_price() > 0


# ---------- llm 纯函数 ----------
def test_backoff_delay():
    assert _backoff_delay(1) == 0.5
    assert _backoff_delay(2) == 1.0
    assert _backoff_delay(3) == 2.0


def test_build_prompt():
    prompt = build_prompt(_sample_news())
    assert "JSON" in prompt, "DeepSeek json_object 模式要求 prompt 含 JSON 字样"
    assert "AI 编程助手进入团队协作" in prompt, "新闻标题应进 prompt"


def test_parse_report_json():
    bare = {"digest": "总览", "items": [{"title": "t", "summary": "s", "comment": "c"}]}
    assert parse_report_json(json.dumps(bare, ensure_ascii=False)).digest == "总览"

    fenced = f"```json\n{json.dumps(bare, ensure_ascii=False)}\n```"
    assert parse_report_json(fenced).items[0].comment == "c"

    with pytest.raises(ValueError):
        parse_report_json("这不是 JSON")
    with pytest.raises(ValueError):
        parse_report_json('{"digest": "缺 items 字段"}')  # 缺必填字段 -> 校验失败 -> 可重试


# ---------- news 跳过策略（离线，monkeypatch）----------
def test_fetch_all_skips_broken_source(monkeypatch):
    import app.news as news_mod

    good = [NewsItem(title="好的新闻", source="少数派")]
    calls = []

    def fake_fetch(url):
        calls.append(url)
        if "solidot" in url:
            raise httpx.ConnectError("模拟源挂了", request=None)
        return good

    monkeypatch.setattr(news_mod, "fetch_feed", fake_fetch)
    items = news_mod.fetch_all()          # 默认 NEWS_SOURCES 里必含 solidot
    assert [items[0]] == good
    assert len(calls) == len(news_mod.NEWS_SOURCES), "坏源不阻断其余源"


# ---------- 路由（离线，dependency_overrides）----------
def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_provider_no_key_leak():
    r = client.get("/provider")
    assert r.status_code == 200
    body = r.text
    assert "base_url" in body and "model" in body
    assert "sk-" not in body, "api_key 绝不能出现在响应里"

@pytest.mark.skipif(
        not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ZHIPU_API_KEY")),
        reason="需要真实 API Key 的冒烟测试，CI 无密钥环境自动跳过"
)
def test_news_translates_no_news_to_503(monkeypatch):
    from app.main import get_report_provider
    def broken_provider():
        def _raise():
            raise NoNewsError("所有新闻源都失败了")
        return _raise

    app.dependency_overrides[get_report_provider] = broken_provider
    try:
        r = client.get("/news")
        assert r.status_code == 503, f"无素材应 503，实际 {r.status_code}"
        assert "新闻源" in r.json()["detail"]
    finally:
        app.dependency_overrides.clear()


# ---------- 真实链路（RSS + LLM）----------
@pytest.mark.skipif(
        not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ZHIPU_API_KEY")),
        reason="需要真实 API Key 的冒烟测试，CI 无密钥环境自动跳过"
)
def test_news_real_end_to_end():
    report = client.get("/news").json()
    assert report["report_date"] == str(date.today())
    assert 3 <= len(report["items"]) <= 5, f"契约要求 3–5 条，实际 {len(report['items'])}"
    for item in report["items"]:
        assert item["title"] and item["comment"], f"要点缺 title/comment: {item}"
    assert len(report["digest"]) <= 250, "digest 应在 150 字左右（宽松校验 250）"
