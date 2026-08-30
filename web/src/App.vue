<script setup>
// App.vue 是唯一的状态持有处（单页应用，不用 Pinia）：
// 网络收口在 api.js，子组件只吃 props；状态机见任务书 4.2：
//   idle ──点击生成──> fetching_news ──phase帧──> generating ──report帧──> done
//     ▲                  │                        │                     │
//     └──────────────────┴──── error 帧 / 断流 ────┴─────────────────────┘
import { computed, onMounted, ref } from 'vue'
import { checkHealth, startReportStream } from './api'
import PhaseBanner from './components/PhaseBanner.vue'
import DigestTypewriter from './components/DigestTypewriter.vue'
import NewsCard from './components/NewsCard.vue'
import CostBadge from './components/CostBadge.vue'
import ErrorBanner from './components/ErrorBanner.vue'

// —— 核心状态 ——
const status = ref('idle')       // idle | fetching_news | generating | done | error
const errorMessage = ref('')     // error 帧或断流的原因
const digest = ref('')           // digest 增量拼接结果
const report = ref(null)         // report 帧内容，可能缺席（渲染前判空）
const cost = ref(null)           // usage 帧里的 cost，可能缺席（null 则不显示徽章）
const healthOk = ref(null)       // null=检测中，true/false 为检测结果

const isRunning = computed(() => status.value === 'fetching_news' || status.value === 'generating')
const items = computed(() =>
  report.value && Array.isArray(report.value.items) ? report.value.items : [],
)
const healthText = computed(() =>
  healthOk.value === null ? '检测中' : healthOk.value ? '服务正常' : '服务不可用',
)
// 底栏只在有内容可展示时出现（生成中 / 已完成 / 已产生成本）
const showBottomBar = computed(
  () => isRunning.value || status.value === 'done' || cost.value !== null,
)

/** 点击「生成今日早报 / 重新生成」：重置本轮数据并重新订阅 SSE 流 */
function startReport() {
  if (isRunning.value) return // 铁律兜底：生成中不允许重复触发（按钮本身已 disabled）
  status.value = 'fetching_news'
  errorMessage.value = ''
  digest.value = ''
  report.value = null
  cost.value = null
  startReportStream({
    onPhase: (phase) => {
      status.value = phase === 'fetching_news' ? 'fetching_news' : 'generating'
    },
    onContent: (chunk) => {
      // 容错：若后端未发 generating 帧就直接开始吐文本，横幅同步切换
      if (status.value === 'fetching_news') status.value = 'generating'
      digest.value += chunk
    },
    onReport: (r) => {
      // 状态机：report 帧到达即视为 done（usage/[DONE] 由 api.js 继续收完）
      report.value = r
      if (status.value !== 'error') status.value = 'done'
    },
    onUsage: (frame) => {
      if (frame && typeof frame.cost === 'number') cost.value = frame.cost
    },
    onError: (message) => {
      status.value = 'error'
      errorMessage.value = message
    },
    onDone: () => {
      if (status.value !== 'error') status.value = 'done'
    },
  })
}

// 顶部健康状态点：只检测一次，失败/超时显示灰色，不影响主流程
onMounted(() => {
  checkHealth().then((ok) => {
    healthOk.value = ok
  })
})
</script>

<template>
  <div class="app-shell">
    <!-- 顶栏：产品名 + 健康状态点 -->
    <header class="topbar">
      <div class="topbar-inner">
        <div class="brand">
          <svg class="brand-icon" viewBox="0 0 24 24" width="18" height="18" aria-hidden="true">
            <circle cx="12" cy="12" r="4.5" fill="var(--color-primary)" />
            <g stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round">
              <line x1="12" y1="2" x2="12" y2="4.5" />
              <line x1="12" y1="19.5" x2="12" y2="22" />
              <line x1="2" y1="12" x2="4.5" y2="12" />
              <line x1="19.5" y1="12" x2="22" y2="12" />
              <line x1="4.9" y1="4.9" x2="6.7" y2="6.7" />
              <line x1="17.3" y1="17.3" x2="19.1" y2="19.1" />
              <line x1="4.9" y1="19.1" x2="6.7" y2="17.3" />
              <line x1="17.3" y1="6.7" x2="19.1" y2="4.9" />
            </g>
          </svg>
          <span class="brand-name">热点早报</span>
        </div>
        <div class="health" :class="{ ok: healthOk === true }">
          <span class="dot"></span>
          <span>{{ healthText }}</span>
        </div>
      </div>
    </header>

    <!-- 单列主体：max-width 760px 居中 -->
    <main class="page">
      <section v-if="status === 'idle' || status === 'error'" class="hero">
        <button class="btn-primary" type="button" @click="startReport">生成今日早报</button>
        <p class="hero-hint">聚合当日中文科技 RSS 源，AI 撰写 3 分钟可读的速览早报</p>
      </section>

      <PhaseBanner v-if="isRunning" :phase="status" />

      <ErrorBanner v-if="status === 'error'" :message="errorMessage" />

      <DigestTypewriter v-if="digest" :text="digest" :running="status === 'generating'" />

      <section v-if="items.length" class="news-section">
        <h2 class="section-title">今日要点</h2>
        <!-- items 与 report 帧一起整体替换，用下标作 key 即可 -->
        <div class="card-grid">
          <NewsCard v-for="(item, index) in items" :key="index" :item="item" />
        </div>
      </section>
    </main>

    <!-- 底栏：本次成本 + 主按钮（生成中 disabled + spinner） -->
    <footer v-if="showBottomBar" class="bottombar">
      <div class="bottombar-inner">
        <CostBadge v-if="cost !== null" class="cost" :cost="cost" />
        <button v-if="isRunning" class="btn-primary" type="button" disabled>
          <span class="spinner" aria-hidden="true"></span>
          生成中…
        </button>
        <button v-else-if="status === 'done'" class="btn-primary" type="button" @click="startReport">
          重新生成
        </button>
      </div>
    </footer>
  </div>
</template>

<style scoped>
.app-shell {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

/* —— 顶栏 —— */
.topbar {
  background: var(--color-card);
  border-bottom: 1px solid var(--color-border);
}
.topbar-inner {
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-2) var(--space-3);
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.brand {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  font-size: 17px;
  font-weight: 600;
}
.health {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: var(--radius-badge);
  background: var(--color-text-secondary);
}
.health.ok .dot {
  background: var(--color-success);
}

/* —— 主体 —— */
.page {
  width: 100%;
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-4) var(--space-3);
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}
.hero {
  text-align: center;
  padding: var(--space-4) 0;
}
.hero-hint {
  margin: var(--space-2) 0 0;
  font-size: 12px;
  color: var(--color-text-secondary);
}
.section-title {
  margin: 0 0 var(--space-2);
  font-size: 15px;
  font-weight: 600;
}
.card-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-2);
}

/* —— 主按钮 —— */
.btn-primary {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: var(--radius-button);
  padding: 10px 20px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
  transition: background 150ms ease;
}
.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-strong);
}
.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.spinner {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-badge);
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: #fff;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* —— 底栏 —— */
.bottombar {
  position: sticky;
  bottom: 0;
  background: var(--color-card);
  border-top: 1px solid var(--color-border);
}
.bottombar-inner {
  max-width: 760px;
  margin: 0 auto;
  padding: var(--space-2) var(--space-3);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}
.cost {
  margin-right: auto; /* 有成本徽章时靠左，按钮始终靠右 */
}

/* —— 响应式断点 640px：卡片 2 列 → 1 列，内边距收缩 —— */
@media (max-width: 640px) {
  .page {
    padding: var(--space-3) var(--space-2);
  }
  .card-grid {
    grid-template-columns: 1fr;
  }
}
</style>
