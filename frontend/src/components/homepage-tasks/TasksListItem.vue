<template>
  <div class="card">
    <div class="header">
      <img alt="user header" :src="task.icon" />
      <div v-tooltip.left="task.tooltipData" autoHide="false">
        <circle-help />
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
  color: var(--color-icon-muted);
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
  color: var(--color-text-muted);
  font-size: 14px;
  line-height: 1.42;
}
.footer {
}
.w-full {
}
</style>
