<template>
  <div class="card">
    <div class="header">
      <img class="image" alt="" :src="task.icon" width="48" height="48" />
      <div v-tooltip.left="task.tooltipData" autoHide="false">
        <circle-help :size="20" class="tooltip-icon"/>
      </div>
    </div>
    <div class="content">
      <div class="card-title">
        {{ task.title }}
      </div>
      <div class="text">
        <p>
          {{ task.description }}
        </p>
      </div>
    </div>
    <div class="footer" v-if="task.btnText">
      <d-button :label="task.btnText" severity="secondary" class="w-full" @click="onButtonClick" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { TaskData } from './interfaces'

import { CircleHelp } from 'lucide-vue-next'

import { useRouter } from 'vue-router'

type TProps = {
  task: TaskData
}

const props = defineProps<TProps>()

const router = useRouter()

function onButtonClick() {
  if (props.task.linkName) router.push({ name: props.task.linkName })
}
</script>

<style scoped>
.card {
  padding: 24px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
}
.header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: 16px;
  color: var(--p-icon-muted-color);
}
.image {
  width: 48px;
  height: 48px;
}
.content {
  display: flex;
  flex-direction: column;
}
.content:not(:last-child) {
  margin-bottom: 24px;
}
.card-title {
  font-size: 20px;
  font-weight: 500;
  line-height: 1.2;
  margin-bottom: 8px;
}
.text {
  color: var(--p-text-muted-color);
  font-size: 14px;
  line-height: 1.42;
}
@media (max-width: 768px) {
  .tooltip-icon {
    display: none;
  }
  .card {
    padding: 15px;
  }
}
</style>
