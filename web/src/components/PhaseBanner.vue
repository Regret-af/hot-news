<script setup>
// 阶段横幅：把 phase 翻译成文案（fetching_news → 抓取中，generating → 撰写中）
// 仅在非 idle 的运行中状态由 App.vue 渲染
defineProps({
  phase: { type: String, required: true },
})
</script>

<template>
  <div class="phase-banner" role="status">
    <span class="arrow" aria-hidden="true">▸</span>
    <span>{{ phase === 'fetching_news' ? '正在抓取新闻源…' : 'AI 正在撰写早报…' }}</span>
  </div>
</template>

<style scoped>
.phase-banner {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 10px var(--space-3);
  border-radius: var(--radius-button);
  background: rgba(47, 107, 255, 0.08); /* 主色同色系浅底 */
  color: var(--color-primary);
  font-size: 14px;
  font-weight: 500;
}
.arrow {
  animation: pulse 1.2s ease-in-out infinite;
}
@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.3;
  }
}
</style>
