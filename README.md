# 热点早报生成器（Hot News）

> 上班族没时间刷资讯——每天一份 3 分钟 AI 早报：抓取科技圈热点，大模型生成摘要与点评，SSE 流式输出打字机效果。

阶段 0 热身项目 · 2026-09 · 后端 Python/FastAPI · 前端 Vue3

<!-- 演示 GIF 占位：docs/demo.gif（如补录，取消注释） -->
<!-- ![demo](docs/demo.gif) -->

## 功能

- ✅ `GET /health` 健康检查（前端顶部状态点）
- ✅ `GET /news` 结构化早报（JSON）：总览摘要 + 3–5 条带 AI 点评的要点
- ✅ `GET /news/stream` SSE 流式输出（打字机效果，阶段横幅 + 成本徽章）
- ✅ `GET /provider` 当前厂商信息（不含密钥）
- ✅ 容错：RSS 单源失败自动跳过 · LLM 超时/断网/429 指数退避重试 · 4xx 快速失败 · 畸形 JSON 计入重试

## 架构

```
RSS 源 ×3 ──feedparser──> news.py   fetch_feed()（单源，异常上抛）
                        fetch_all()（聚合，坏源跳过 warning）
                                     │ list[NewsItem]
config.py（.env / ProviderConfig）──> llm.py
                        段1 stream_digest：流式生成 digest（增量事件）
                        段2 _generate_items：JSON mode 生成要点（分层重试）
                        usage 两段聚合 → cost
                                     │ 类型化元组事件
main.py  GET /news（JSON）·  GET /news/stream（SSE）·  /health · /provider
                        路由层只做参数校验与异常翻译（NoNewsError→503 / LLMError→502）
```

前后端契约：`docs/frontend-brief.md`（本地文档，定义帧协议、状态机与视觉规范）。

## SSE 帧协议

`Content-Type: text/event-stream` · `Cache-Control: no-cache`，每帧 `data: <JSON>\n\n`，按到达顺序：

| 顺序 | 帧 | 说明 |
|---|---|---|
| 1 | `{"phase": "fetching_news"}` | 正在抓取新闻源 |
| 2 | `{"phase": "generating"}` | 开始生成早报 |
| 3×N | `{"content": "增量文本"}` | digest 增量（前端拼接为打字机） |
| 4 | `{"report": {…完整 MorningReport…}}` | 收尾：要点卡片渲染 |
| 5 | `{"usage": {…}, "cost": 0.016}` | 本次成本（可缺席，前端容错） |
| ? | `{"error": "消息"}` | 任何时刻可现，出现即终止 |
| 末 | `data: [DONE]` | 结束标记 |

**流式错误处理约定**：首帧发出后 HTTP 状态码已不可变，因此错误一律走 `{"error": ...}` 帧而非状态码；`[DONE]` 与 error 帧后客户端必须关闭连接（防 EventSource 自动重连导致重复生成、重复扣费）。

## 技术决策

**1. 两段式生成，而非单次 JSON 流式调用。**
契约要求 digest 逐字流式（打字机）且 items 带 AI 点评。若用 json_object 模式单次流式，吐出的是原始 JSON 字符——大括号会进打字机。拆成两段：段 1 流式生成自然语言摘要直接喂打字机，段 2 基于同一批新闻 + 已定稿摘要用 JSON mode 产出要点。代价是多一次调用与上下文折损，换来实现简单与打字机纯净度；单次调用 + 增量 JSON 解析是明确的下一步优化。

**2. 分层容错，每层策略不同。**
RSS 单源失败 → 跳过（坏一个源不拖垮整份早报）；LLM 超时/断网/429 → 指数退避重试（网络抖动与限流都是暂时的）；其他 4xx → 不重试直接失败（key 错误重试一万次也一样）；畸形 JSON → 计入重试（模型抽风是暂时的）。策略差异的依据是**故障的可恢复性**，不是统一套一层 retry。

**3. 事件协议：类型化元组 + "kind 即帧键"。**
管线 `yield ("content", 增量)` / `("report", 报告)`，路由层 `sse({kind: data})` 一行组帧——事件类型在协议层固定，不会出现混合类型的 yield。usage 帧是双键帧（usage + cost），由管线组好完整帧体、序列化层原样输出。

## 实验记录（真实数据，2026-09-09，DeepSeek）

**实验一：`response_format=json_object` vs 裸 prompt（各 5 次，同一批 13 条真实新闻）**

| 指标 | json_object | 裸 prompt |
|---|---|---|
| 解析成功率 | 5/5 | 5/5 |
| 输出含 ``` 围栏 | **0/5** | **5/5** |
| 平均 token | 1624 | 1609 |
| 平均延迟 | 14.1s | 16.5s |

结论与预期相反：**json_object 没有提高解析成功率**——项目的容错解析器（剥围栏 + 字段校验）把两种输出全部兜住了。它的真实价值是**消除对容错逻辑的依赖**：输出契约由模型侧保证，而非解析侧兜底；围栏频次 0/5 vs 5/5 是唯一稳定差异。延迟差异在 5 样本噪声内，不作统计结论。

**实验二：流式 usage 帧的三种 payload 形态对照**（嵌套 `stream_options` / 顶层 `include_usage` / 均不带）：当前厂商（DeepSeek）三种形态都返回 usage 帧——该厂商流式 usage 不依赖 opt-in；嵌套规范形仍被采用，理由是跨厂商可移植性。

**成本口径**：费率按简化假设 0.01 元/千 token（与前端成本徽章同口径）。实验中单次完整生成约 1.6K token ≈ 0.016 元；本实验 10 次调用合计约 0.16 元。

## 快速开始

```bash
# 后端（Python 3.12+，uv）
uv sync                          # 按 uv.lock 还原环境
cp .env.example .env             # 填入 DEEPSEEK_API_KEY 或 ZHIPU_API_KEY
uv run uvicorn app.main:app --reload
# 接口文档：http://127.0.0.1:8000/docs

# 前端（Node 20+，Vue3 + Vite）
cd web && npm install
npm run dev                      # Vite proxy 已指向 127.0.0.1:8000
# 无后端演示：VITE_MOCK=true npm run dev（按契约帧序回放内置样例）

# 测试（9 离线 + 4 真实链路）
uv run pytest tests/ -v
```

## 已知限制

- 流式响应中途失败不做自动重试（首帧后重试会导致打字机重复输出），仅非流式 `/news` 具备重试；
- digest 与 items 分两段生成，要点生成看不到摘要的生成过程（prompt 中已注入定稿摘要缓解）；
- 费率为简化假设（0.01 元/千 token），与厂商实际计费可能有出入，仅用于成本量级展示。

## 更新日志

- 2026-09-05 项目骨架（config / schemas / news / llm / main + 前端契约）
- 2026-09-06 非流式链路：RSS 抓取 + JSON mode 摘要 + 分层重试（含 Schema Linking 修复）
- 2026-09-07 SSE 流式管线：两段式生成 + 帧协议对接前端
- 2026-09-09 收尾：前端验收通过、实验记录、README 成稿
