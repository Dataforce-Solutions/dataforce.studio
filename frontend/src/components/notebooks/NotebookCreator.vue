<template>
  <div>
    <Button label="Create notebook" @click="visible = true" />
    <Dialog v-model:visible="visible" modal header="Create Notebook" :style="{ width: '25rem' }">
      <NotebookCreateUpdateForm :loading="loading" @submit="onSubmit"></NotebookCreateUpdateForm>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { Button, Dialog, useToast } from 'primevue'
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue'
import { useNotebooksStore } from '@/stores/notebooks'

const notebooksStore = useNotebooksStore()
const toast = useToast()

const visible = ref(false)
const loading = ref(false)

async function onSubmit(payload: { fullname: string }) {
  loading.value = true
  await notebooksStore.create(payload)
  loading.value = false
  visible.value = false
  toast.add({ severity: 'success', summary: 'Success', detail: 'Notebook Created', life: 2000 })
}
</script>

<style scoped></style>
