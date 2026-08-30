# 热点早报生成器（Hot News）

> 上班族没时间刷资讯——每天一份 3 分钟 AI 早报：抓取科技圈热点，AI 摘要 + 点评，流式输出打字机效果。

**状态**：开发中（阶段 0 热身项目，2026-09）

## 功能

- [ ] `GET /health` 健康检查
- [ ] `GET /news` 生成结构化早报（JSON）：热点列表 + AI 摘要 + 点评
- [ ] `GET /news/stream` SSE 流式输出（打字机效果）
- [ ] 新闻源失败自动跳过、LLM 调用重试（429 退避）

## 技术栈

Python 3.12 · FastAPI · httpx · feedparser · pydantic v2 · uv

## 快速开始

```bash
uv sync                # 按 uv.lock 还原环境
cp .env.example .env   # 填入你的 API Key
uv run uvicorn app.main:app --reload
# 打开 http://127.0.0.1:8000/docs
```

## 架构

```
RSS 源（2–3 个）──feedparser──> news.py  fetch_all()
                                     │
config.py（.env）──> llm.py  build_prompt() / chat_json() / stream_report()
                                     │
main.py  GET /news（JSON）·  GET /news/stream（SSE 打字机）·  GET /health
```

## 更新日志

- 2026-09-05 项目骨架建立
