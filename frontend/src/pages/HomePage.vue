<template>
  <div class="content">
    <div class="headings">
      <h1 class="main-title">Pick a machine learning task</h1>
      <p class="sub-title">
        Choose from a variety of tasks that best fit your needs, or explore them all to discover new
        possibilities.
      </p>
    </div>
    <div class="body">
      <tasks-list label="Now available" :tasks="availableTasks" />
      <div class="divider"></div>
      <tasks-list label="Coming soon" :tasks="notAvailableTasks" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'

import TasksList from '@/components/homepage-tasks/TasksList.vue'

import { useUserStore } from '@/stores/user'
import { useToast } from 'primevue/usetoast'

import { passwordResetSuccessToast } from '@/lib/primevue/data/toasts'
import { availableTasks, notAvailableTasks } from '@/constants/constants'

const userStore = useUserStore()
const toast = useToast()

const showPasswordMessage = () => {
  toast.add(passwordResetSuccessToast)
}

onMounted(() => {
  userStore.isPasswordHasBeenChanged && showPasswordMessage()
})
</script>

<style scoped>
.body {
  display: flex;
  flex-direction: column;
  gap: 36px;
}

.content {
  padding-top: 28px;
}

.headings {
  margin-bottom: 44px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}
</style>
