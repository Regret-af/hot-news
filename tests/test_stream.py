# -*- coding: utf-8 -*-
"""
运行（项目根目录）：uv run pytest tests/test_stream.py -v
"""
import json
import os

import pytest
from fastapi.testclient import TestClient

import app.main as main_mod
from app.errors import LLMError, NoNewsError
from app.main import app
from app.schemas import NewsItem
from app.main import app, get_stream_digest

client = TestClient(app)


def _sample_news() -> list[NewsItem]:
    return [NewsItem(title="AI 编程助手进入团队协作", summary="评审轮次减少", source="少数派", url="https://a/1")]


def _fake_pipeline(news):
    """离线假管线：按事件协议回放一整条流（fetching_news 由路由层发，管线从 generating 起）"""
    for piece in ["早报君：", "今天的关键词是", "「务实」。"]:
        yield ("content", piece)
    yield ("report", {
        "report_date": "2026-09-07",
        "digest": "早报君：今天的关键词是「务实」。",
        "items": [{"title": "AI 编程助手进入团队协作", "summary": "评审轮次减少",
                   "comment": "瓶颈从写码转向审码。", "source": "少数派", "url": "https://a/1"}],
    })
    yield ("usage", {"usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
                     "cost": 0.00015})


def _sse_lines(response) -> list[str]:
    """从流式响应收集全部 data: 行（在 stream 上下文内调用）"""
    return [ln for ln in response.iter_lines() if ln.startswith("data: ")]


def _frames(lines: list[str]) -> list[dict]:
    return [json.loads(ln[6:]) for ln in lines if ln != "data: [DONE]"]


# ---------- 路由（离线，dependency_overrides）----------
def test_stream_frame_sequence_offline(monkeypatch):
    monkeypatch.setattr(main_mod, "fetch_all", lambda: _sample_news())
    app.dependency_overrides[get_stream_digest] = lambda: _fake_pipeline
    try:
        with client.stream("GET", "/news/stream") as r:
            assert r.status_code == 200
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers.get("cache-control") is not None, "契约要求 no-cache"

            lines = _sse_lines(r)
            assert lines[-1] == "data: [DONE]"
            frames = [json.loads(ln[6:]) for ln in lines[:-1]]

        # 契约帧序：fetching_news（路由层）→ generating（管线）→ content×N → report → usage
        assert frames[0] == {"phase": "fetching_news"}
        assert frames[1] == {"phase": "generating"}
        assert [f["content"] for f in frames[2:5]] == ["早报君：", "今天的关键词是", "「务实」。"]
        assert frames[5]["report"]["items"][0]["comment"] == "瓶颈从写码转向审码。"
        # 契约 3.3 帧 5：{"usage": {...}, "cost": ...}——单层，usage 与 cost 平级
        assert frames[6]["usage"]["total_tokens"] == 150
        assert frames[6]["cost"] == 0.00015
    finally:
        app.dependency_overrides.clear()


def test_stream_error_frame(monkeypatch):
    monkeypatch.setattr(main_mod, "fetch_all", lambda: [])

    def broken_pipeline(news):
        yield ("phase", "generating")
        raise LLMError("模拟上游故障")

    app.dependency_overrides[get_stream_digest] = lambda: broken_pipeline
    try:
        with client.stream("GET", "/news/stream") as r:
            lines = _sse_lines(r)
        frames = _frames(lines)
        assert any("error" in f for f in frames), f"应有错误帧: {frames}"
        assert lines[-1] == "data: [DONE]", "错误帧之后仍要有 [DONE] 收尾"
    finally:
        app.dependency_overrides.clear()


def test_stream_no_news_error_frame(monkeypatch):
    monkeypatch.setattr(main_mod, "fetch_all", lambda: [])
    with client.stream("GET", "/news/stream") as r:
        lines = _sse_lines(r)
    frames = _frames(lines)
    assert any(f.get("error") for f in frames), f"无素材应走错误帧: {frames}"
    assert lines[-1] == "data: [DONE]"


# ---------- 真实流式（RSS + 两段 LLM）----------
@pytest.mark.skipif(
        not (os.environ.get("DEEPSEEK_API_KEY") or os.environ.get("ZHIPU_API_KEY")),
        reason="需要真实 API Key 的冒烟测试，CI 无密钥环境自动跳过"
)
def test_stream_real_end_to_end():
    with client.stream("GET", "/news/stream") as r:
        lines = _sse_lines(r)
    assert lines[-1] == "data: [DONE]"
    frames = [json.loads(ln[6:]) for ln in lines[:-1]]

    assert any("phase" in f for f in frames), "缺 phase 帧"
    assert not any("error" in f for f in frames), f"真实链路不应出错: {frames}"
    contents = "".join(f["content"] for f in frames if "content" in f)
    reports = [f["report"] for f in frames if "report" in f]
    usages = [f for f in frames if "usage" in f]

    assert reports, "缺 report 帧"
    report = reports[0]
    assert contents == report["digest"], "content 拼接必须与 report.digest 逐字一致（两段式一致性）"
    assert 3 <= len(report["items"]) <= 5 and all(i["comment"] for i in report["items"])
    assert usages, "usage 帧应存在（两段聚合）"
    assert usages[0]["cost"] > 0
