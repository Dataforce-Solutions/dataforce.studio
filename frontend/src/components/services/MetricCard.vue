<template>
  <div class="metric">
    <h3 class="metric-title">{{ title }}</h3>
    <div class="results">
      <div class="result" v-for="item in items" :key="item.id" :class="{ primary: item.primary }">
        <h4 class="label">{{ item.label }}</h4>
        <div class="value">{{ item.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IMetricCard } from './services.interfaces'

defineProps<IMetricCard>()
</script>

<style scoped>
.metric {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  box-shadow: var(--card-shadow);
}
.metric-title {
  margin-bottom: 16px;
}
.results {
  display: flex;
  gap: 52px;
}
.result {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.label {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.value {
  line-height: 1.5;
}

.primary {
  color: var(--color-primary);
}

.primary .label {
  color: var(--color-primary);
}

.primary .value {
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
}
</style>
