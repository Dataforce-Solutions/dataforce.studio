<template>
  <tasks-list label="Now available" :tasks="availableTasks" />
</template>

<script setup lang="ts">
import TasksList from './TasksList.vue'
import { availableTasks } from './data'
</script>

<style scoped></style>
