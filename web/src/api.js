// 网络层（唯一收口）：所有请求只允许写在这里，组件不得直接发请求。
// 契约来源：docs/frontend-brief.md 第 3 节（接口）、6.2 节（本文件形态）。

// —— 可选 mock 模式（任务书加分项）：设置 VITE_MOCK=true 开启，默认关闭 ——
// 后端未就绪时，用内置样例帧按真实协议顺序回放，方便前端独立演示。
// 只改数据来源，onXxx 回调与真实链路完全一致；不影响默认的真实请求路径。
const MOCK = import.meta.env.VITE_MOCK === 'true'

// —— mock 样例数据（仅在 VITE_MOCK=true 时使用）——
const MOCK_DIGEST = '早报君：今天科技圈的关键词是「务实」。AI 编程助手进入团队协作流程，工程效率有了可量化的提升；开源社区在推理框架上拿下关键一城；终端厂商开始重新规划中端产品的配置策略。三分钟，带你过完今天值得知道的一切。'
// 把整段 digest 预切成增量片段，模拟流式输出节奏
const MOCK_CHUNKS = MOCK_DIGEST.match(/.{1,14}/g) || [MOCK_DIGEST]
const MOCK_REPORT = {
  report_date: '2026-08-30',
  digest: MOCK_DIGEST,
  items: [
    {
      title: 'AI 编程助手进入团队协作流程，代码评审效率提升约三成',
      summary: '多家团队披露落地数据：AI 助手承担初稿与重构建议后，评审轮次明显减少，但安全审计环节仍需人工把关。',
      comment: '工具提效是真的，瓶颈正在从「写代码」转移到「审代码」。',
      source: '少数派',
      url: 'https://example.com/mock/1',
    },
    {
      title: '开源推理框架发布新版本，长文本吞吐翻倍',
      summary: '新版本重写了 KV 缓存管理，官方基准显示长上下文场景吞吐提升约一倍，社区贡献者占比过半。',
      comment: '上游基建的每一次提效，最终都会折算成应用层的成本下降。',
      source: '爱范儿',
    },
    {
      title: '中端机型配置策略生变：芯片降价传导至终端',
      summary: '供应链消息称中端 SoC 价格回落，厂商计划把原本旗舰级的存储组合下放到 2000 元档。',
      comment: '对消费者是好事，但也说明增量市场见顶，只能靠配置卷存量。',
      url: 'https://example.com/mock/3',
    },
    {
      title: '折叠屏维修新政落地，官方维修价首次低于保外费用',
      summary: '主流厂商同步下调折叠屏铰链与内屏的官方维修定价，并推出意外保障服务包。',
      comment: '维修定价松口，说明折叠屏开始按「主流第二台手机」来经营口碑。',
    },
  ],
}
const MOCK_USAGE_FRAME = {
  usage: { prompt_tokens: 156, completion_tokens: 214, total_tokens: 370 },
  cost: 0.000021,
}

// mock 回放用的定时器集合与代次号：重新生成时清空旧定时器并使旧回调失效，
// 用来模拟「旧连接已被 close」的语义（对应真实模式的 activeEs 兜底）。
let mockTimers = []
let mockSeq = 0

// 真实模式下当前打开的 EventSource。正常流程中 DONE / error 帧都会 close 并置空，
// 这里再兜底一层：若上一次流因任何原因没关，开始新一次生成前强制关闭，防止双流重复计费。
let activeEs = null

/**
 * 健康检查：接口 ok 返回 true；网络失败 / 超时 / 非 2xx 一律返回 false。
 * 只影响顶部状态点（绿/灰），不参与主流程。
 */
export function checkHealth() {
  if (MOCK) return Promise.resolve(true)
  const ctrl = new AbortController()
  const timer = setTimeout(() => ctrl.abort(), 5000) // 5 秒超时，避免状态点长期悬空
  return fetch('/health', { signal: ctrl.signal })
    .then((r) => r.ok)
    .catch(() => false)
    .finally(() => clearTimeout(timer))
}

/**
 * 订阅 SSE 早报生成流（GET /news/stream）。
 * 回调：onPhase(phase) / onContent(增量) / onReport(完整报告) /
 *       onUsage(整帧，含 usage 与 cost，可能缺席) / onError(消息) / onDone()
 *
 * 生命周期铁律（任务书 3.3，不可违反）：
 * 1. 收到 [DONE] 或 error 帧后必须 es.close()，否则 EventSource 自动重连会导致重复生成、重复扣费；
 * 2. es.onerror 同样 close 并转错误回调，防止无限重连；
 * 3. HTTP 层错误（如 503）在 EventSource 里同样表现为 onerror，与 error 帧同等处理。
 */
export function startReportStream({ onPhase, onContent, onReport, onUsage, onError, onDone }) {
  if (MOCK) return startMockStream({ onPhase, onContent, onReport, onUsage, onError, onDone })

  if (activeEs) activeEs.close() // 兜底：关掉上次未关闭的连接
  const es = new EventSource('/news/stream')
  activeEs = es

  // settled 保证终态只触发一次：error 帧之后到达的 [DONE]、或收尾竞态不再改写结果
  let settled = false
  const finish = () => {
    if (settled) return
    settled = true
    es.close() // 铁律：DONE 必须 close
    activeEs = null
    onDone()
  }
  const fail = (message) => {
    if (settled) return
    settled = true
    es.close() // 铁律：错误帧必须 close
    activeEs = null
    onError(message)
  }

  es.onmessage = (e) => {
    if (e.data === '[DONE]') return finish()
    let frame
    try {
      frame = JSON.parse(e.data)
    } catch {
      // 防御：无法解析的帧按错误处理并断开，避免连接悬死在无响应状态
      return fail('收到无法解析的数据帧')
    }
    if (frame.error) return fail(frame.error)
    if (frame.phase) return onPhase(frame.phase)
    if (frame.content) return onContent(frame.content)
    if (frame.report) return onReport(frame.report)
    if (frame.usage) return onUsage(frame)
  }
  es.onerror = () => fail('连接中断，请稍后重试') // 铁律：close 防自动重连
}

/** mock 回放：按契约 3.3 的帧顺序 + 模拟流式节奏调用同一组回调 */
function startMockStream({ onPhase, onContent, onReport, onUsage, onError, onDone }) {
  clearMock()
  const seq = ++mockSeq
  const at = (delay, fn) => {
    mockTimers.push(
      setTimeout(() => {
        if (seq === mockSeq) fn() // 代次不匹配说明已被新一轮生成作废
      }, delay),
    )
  }

  at(0, () => onPhase('fetching_news'))
  at(800, () => onPhase('generating'))
  let t = 1500
  for (const chunk of MOCK_CHUNKS) {
    at(t, () => onContent(chunk))
    t += 130
  }
  at((t += 400), () => onReport(MOCK_REPORT))
  at((t += 300), () => onUsage(MOCK_USAGE_FRAME))
  at((t += 250), () => onDone())
  // onError 仅保留形参占位：mock 数据不含错误路径，真实错误路径请用真实后端验证
  void onError
}

function clearMock() {
  for (const timer of mockTimers) clearTimeout(timer)
  mockTimers = []
}
