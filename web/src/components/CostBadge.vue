<script setup>
// 成本徽章：展示本次生成的成本（usage 帧，可能缺席——父组件判空后才渲染本组件）
import { computed } from 'vue'

const props = defineProps({
  cost: { type: Number, required: true },
})

// 小额成本保留 6 位小数（与契约示例 ¥0.000016 对齐），较大金额保留 2 位，
// 同时避免 JS 数字转字符串时出现科学计数法
const label = computed(() => {
  const value = props.cost
  const text = value < 0.01 ? value.toFixed(6) : value.toFixed(2)
  return `本次生成 ≈ ¥${text}`
})
</script>

<template>
  <span class="cost-badge">{{ label }}</span>
</template>

<style scoped>
.cost-badge {
  font-size: 12px;
  color: var(--color-text-secondary);
  background: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-badge);
  padding: 4px 12px;
  white-space: nowrap;
}
</style>
