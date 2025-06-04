<template>
  <div class="notebooks">
    <div class="top">
      <div class="headings">
        <h1 class="main-title">Notebooks</h1>
        <p class="sub-title">All your notebooks will be here</p>
      </div>
      <NotebookCreator></NotebookCreator>
    </div>
    <NotebooksList></NotebooksList>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import NotebooksList from './NotebooksList.vue'
import NotebookCreator from './NotebookCreator.vue'
import { useNotebooksStore } from '@/stores/notebooks'
import { useToast } from 'primevue'

const notebooksStore = useNotebooksStore()
const toast = useToast()

const loading = ref(false)

onMounted(async () => {
  try {
    loading.value = true
    await notebooksStore.getNotebooks()
  } catch {
    toast.add({
      severity: 'error',
      summary: 'Error',
      detail: 'Failed to receive notebooks',
      life: 2000,
    })
  } finally {
    loading.value = false
  }
})
</script>

<style scoped>
.top {
  display: flex;
  justify-content: space-between;
  gap: 30px;
  align-items: flex-end;
  margin-bottom: 20px;
}
</style>
