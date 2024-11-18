<template>
  <tasks-list label="Coming soon" :tasks="notAvailableTasks" />
</template>

<script setup lang="ts">
import TasksList from './TasksList.vue'
import { notAvailableTasks } from './data'
</script>

<style scoped></style>
