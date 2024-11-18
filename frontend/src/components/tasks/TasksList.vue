<template>
  <div class="wrapper">
    <h2 class="label">{{ label }}</h2>
    <div class="items">
      <tasks-list-item v-for="task in tasks" :task="task" :key="task.id" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ITasksList } from './types'
import TasksListItem from './TasksListItem.vue'

defineProps<ITasksList>()
</script>

<style scoped>
.items {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 24px;
}
.label {
    margin-bottom: 20px;
}
</style>
