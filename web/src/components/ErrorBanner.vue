<script setup>
// 错误横幅：error 帧 / 断流 / HTTP 层错误统一由 App.vue 走到这里展示
defineProps({
  message: { type: String, required: true },
})
</script>

<template>
  <div class="error-banner" role="alert">
    <span class="mark" aria-hidden="true">!</span>
    <span>{{ message }}</span>
  </div>
</template>

<style scoped>
.error-banner {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: 10px var(--space-3);
  border-radius: var(--radius-button);
  background: var(--color-danger-bg);
  color: var(--color-danger-text);
  font-size: 14px;
}
.mark {
  flex: none;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-badge);
  background: var(--color-danger-text);
  color: #fff;
  display: grid;
  place-items: center;
  font-size: 12px;
  font-weight: 700;
}
</style>
