<template>
  <div>
    <div class="headings">
      <h1 class="main-title">Pick a machine learning task</h1>
      <p class="sub-title">
        Choose from a variety of tasks that best fit your needs, or explore them all to discover new
        possibilities.
      </p>
    </div>
    <div class="body">
      <available-tasks />
      <div class="divider"></div>
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
  margin-bottom: 44px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
