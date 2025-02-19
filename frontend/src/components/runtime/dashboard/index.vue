<template>
  <component v-if="component" :is="component" :model="model" :current-task="currentTask" />
  <div v-else class="placeholder">
    <h2 class="title">Incorrect model</h2>
    <d-button @click="$emit('exit')">Go back</d-button>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import TabularTask from './tabular/index.vue'
import type { Model } from '@fnnx/web'
import { Tasks } from '@/lib/data-processing/interfaces'

type Props = {
  currentTask: Tasks.TABULAR_CLASSIFICATION | Tasks.TABULAR_REGRESSION
  model: Model
}
type Emits = {
  exit: void
}

const props = defineProps<Props>()
defineEmits<Emits>()

const component = computed(() => {
  if (
    props.currentTask === Tasks.TABULAR_CLASSIFICATION ||
    props.currentTask === Tasks.TABULAR_REGRESSION
  ) {
    return TabularTask
  }
  return null
})
</script>

<style scoped>
.placeholder {
  display: flex;
  flex-direction: column;
  gap: 15px;
  align-items: flex-start;
  padding: 15px;
}
</style>
