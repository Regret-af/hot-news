<script setup>
// 单张要点卡片：字段全部来自 report 帧的 item。
// 契约约定 source / url 可能缺失（3.2 节），对应元素判空不渲染。
defineProps({
  item: { type: Object, required: true },
})
</script>

<template>
  <article class="news-card">
    <span v-if="item.source" class="source-badge">{{ item.source }}</span>
    <h3 class="title">{{ item.title }}</h3>
    <p class="summary">{{ item.summary }}</p>
    <blockquote v-if="item.comment" class="comment">✦ {{ item.comment }}</blockquote>
    <a
      v-if="item.url"
      class="link"
      :href="item.url"
      target="_blank"
      rel="noopener noreferrer"
    >查看原文 ↗</a>
  </article>
</template>

<style scoped>
.news-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: var(--space-3);
  /* 进入时 200ms 淡入上浮（任务书 5 节） */
  animation: card-in 200ms ease-out both;
}
@keyframes card-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: none;
  }
}

.source-badge {
  align-self: flex-start;
  background: rgba(47, 107, 255, 0.1); /* 浅蓝底小字徽章 */
  color: var(--color-primary);
  font-size: 12px;
  line-height: 1.5;
  padding: 2px 8px;
  border-radius: var(--radius-badge);
}
.title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
  line-height: 1.5;
}
.summary {
  margin: 0;
  font-size: 14px;
  line-height: 1.7;
}
.comment {
  margin: var(--space-1) 0 0;
  padding: 2px 0 2px 10px;
  border-left: 3px solid var(--color-primary); /* 引用样式：左侧 3px 主色竖线 */
  color: var(--color-text-secondary);
  font-size: 14px;
  line-height: 1.7;
}
.link {
  margin-top: auto; /* 卡片高度不齐时链接贴底 */
  padding-top: var(--space-1);
  font-size: 12px;
  color: var(--color-primary);
  text-decoration: none;
}
.link:hover {
  text-decoration: underline;
}
</style>
