<template>
  <div>
    <div class="headings">
      <h1 class="title">Pick a machine learning task</h1>
      <p class="text">
        Choose from a variety of tasks that best fit your needs, or explore them all to discover new
        possibilities.
      </p>
    </div>
    <div class="body">
      <available-tasks />
      <hr size="1" color="#DCE4EF">
      <not-available-tasks />
    </div>
  </div>
</template>

<script setup lang="ts">
import AvailableTasks from '@/components/tasks/AvailableTasks.vue'
import NotAvailableTasks from '@/components/tasks/NotAvailableTasks.vue'
</script>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 36px;
}
.headings {
  margin-bottom: 56px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
