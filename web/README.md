# 热点早报 · 前端（web/）

Vue 3 + Vite 单页应用。接口契约、SSE 帧协议、交互状态机、视觉规范见 `../docs/frontend-brief.md`（唯一契约来源）。

- 技术栈：Vue 3（Composition API，`<script setup>`）+ JavaScript + 原生 `EventSource` / `fetch`，无 UI 组件库、无路由、无状态库
- 前置要求：Node ≥ 22.18（Vite 8 的要求，22 LTS 满足；20.x 需降级 Vite 后使用）
- 后端：FastAPI，开发期默认 `http://127.0.0.1:8000`

## 启动（开发）

```sh
npm install
npm run dev
```

开发服务器默认 `http://localhost:5173`，`/health`、`/news/*` 由 Vite proxy 转发到 `http://127.0.0.1:8000`（见 `vite.config.js`），前端代码里全部使用相对路径。

后端尚未就绪时，可用内置 mock 模式独立演示（默认关闭，不影响真实链路）：

```sh
# bash / Git Bash
VITE_MOCK=true npm run dev
# PowerShell
$env:VITE_MOCK="true"; npm run dev
```

## 构建

```sh
npm run build
```

产物输出到 `dist/`。

## 后端托管（生产）

`npm run build` 后，把 `dist/` 交给后端用 FastAPI `StaticFiles` 以同源方式托管（挂到站点根路径），同源无 CORS 问题；此时不再需要 Vite proxy，前端代码里的相对路径直接命中后端路由。

```sh
npm run preview   # 本地静态预览构建产物（可选）
```
