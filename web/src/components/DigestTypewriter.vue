<script setup>
// digest 打字机区域：文本由 App.vue 拼接增量后传入，
// running=true 时显示闪烁光标 ▮，收尾（report 帧 / error）后光标消失
defineProps({
  text: { type: String, default: '' },
  running: { type: Boolean, default: false },
})
</script>

<template>
  <section class="digest-card">
    <p class="digest" aria-live="polite">
      {{ text }}<span v-if="running" class="cursor" aria-hidden="true">▮</span>
    </p>
  </section>
</template>

<style scoped>
.digest-card {
  background: var(--color-card);
  border-radius: var(--radius-card);
  box-shadow: var(--shadow-card);
  padding: var(--space-3) var(--space-4);
}
.digest {
  margin: 0;
  font-size: 17px;
  line-height: 1.8;
  white-space: pre-wrap; /* 保留后端文本中的换行 */
  overflow-wrap: break-word;
}
.cursor {
  display: inline-block;
  margin-left: 2px;
  color: var(--color-primary);
  animation: blink 1s step-end infinite;
}
@keyframes blink {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0;
  }
}
</style>
