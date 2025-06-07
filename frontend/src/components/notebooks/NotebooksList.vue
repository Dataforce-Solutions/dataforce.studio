<template>
  <DataTable
    v-model:expandedRows="expandedRows"
    dataKey="name"
    :value="notebooksStore.notebooks"
    tableStyle="min-width: 50rem;"
    showGridlines
    stripedRows
    size="small"
  >
    <template #empty>
      <div>You don't have any instances yet...</div>
    </template>
    <Column expander style="width: 30px" />
    <Column field="fullname" header="Name" style="width: 25%"></Column>
    <!-- <Column field="version" header="Version" style="width: 100px"></Column> -->
    <Column field="name" header="Link" style="width: 200px">
      <template #body="slot">
        <Button as="a" label="Open JupyterLab" target="_blank" :href="getLink(slot.data.name)" />
      </template>
    </Column>
    <Column field="createdAt" header="Created">
      <template #body="slot">
        <div>{{ new Date(slot.data.createdAt).toLocaleString() }}</div>
      </template>
    </Column>
    <Column style="width: 150px" header="Actions">
      <template #body="slot">
        <div class="buttons">
          <Button variant="text" size="small" @click="onBackupClick(slot.data.name)">
            <template #icon>
              <DatabaseBackup />
            </template>
          </Button>
          <Button variant="text" size="small" @click="onEditClick(slot.data)">
            <template #icon>
              <Pen />
            </template>
          </Button>
          <Button
            variant="text"
            severity="danger"
            size="small"
            @click="onDeleteClick(slot.data.name)"
          >
            <template #icon>
              <Trash2 />
            </template>
          </Button>
        </div>
      </template>
    </Column>
    <template #expansion="slotProps">
      <div v-if="!slotProps.data.files?.length">No models found.</div>
      <div v-else>
        <h5 style="margin-bottom: 5px">Models:</h5>
        <DataTable :value="slotProps.data.files" size="small">
          <Column field="name" header="Name"></Column>
          <Column field="size" header="Size">
            <template #body="slotProps">
              <div>
                {{
                  slotProps.data.size < 1000
                    ? slotProps.data.size + ' B'
                    : slotProps.data.size < 10000000
                      ? slotProps.data.size / 1000 + ' KB'
                      : slotProps.data.size / 10000000 + ' MB'
                }}
              </div>
            </template>
          </Column>
          <Column field="created" header="Created">
            <template #body="slotProps">
              <div>
                {{ new Date(slotProps.data.created).toLocaleString() }}
              </div>
            </template>
          </Column>
          <Column field="last_modified" header="Updated">
            <template #body="slotProps">
              <div>
                {{ new Date(slotProps.data.last_modified).toLocaleString() }}
              </div>
            </template>
          </Column>
        </DataTable>
      </div>
    </template>
  </DataTable>
  <Dialog v-model:visible="visible" modal header="Rename" :style="{ width: '25rem' }">
    <NotebookCreateUpdateForm
      v-if="editData"
      update-mode
      :initial-data="editData"
      @submit="onUpdateSubmit"
    >
    </NotebookCreateUpdateForm>
  </Dialog>
</template>

<script setup lang="ts">
import type { Notebook } from '@/lib/databases/database.interfaces'
import { computed, ref } from 'vue'
import { DataTable, Column, Button, Dialog, useConfirm, useToast } from 'primevue'
import { Trash2, Pen, DatabaseBackup } from 'lucide-vue-next'
import NotebookCreateUpdateForm from './NotebookCreateUpdateForm.vue'
import { useNotebooksStore } from '@/stores/notebooks'

const notebooksStore = useNotebooksStore()
const toast = useToast()
const confirm = useConfirm()

const visible = ref(false)
const editData = ref<{ fullname?: string } | null>()
const expandedRows = ref({})

const getLink = computed(
  () => (databaseName: string) =>
    import.meta.env.BASE_URL + 'jupyter/lab/index.html?instanceId=' + databaseName,
)

function onDeleteClick(databaseName: string) {
  confirm.require({
    header: 'Are you sure?',
    message: 'Are you sure you want to delete the instance? This action cannot be undone.',
    acceptProps: {
      label: 'Delete',
      severity: 'danger',
    },
    rejectProps: {
      label: 'cancel',
      severity: 'secondary',
    },
    accept: async () => {
      try {
        await notebooksStore.remove(databaseName)
        toast.add({
          severity: 'success',
          summary: 'Success',
          detail: 'Notebook deleted',
          life: 2000,
        })
      } catch (e: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: e?.message || 'Failed to delete the instance',
        })
      }
    },
  })
}
function onEditClick(notebook: Notebook) {
  editData.value = { ...notebook }
  visible.value = true
}
async function onUpdateSubmit(payload: { fullname: string }) {
  visible.value = false
  await notebooksStore.edit({ ...editData.value, fullname: payload.fullname })
  toast.add({ severity: 'success', summary: 'Success', detail: 'Notebook info saved', life: 2000 })
}
function onBackupClick(name: string) {
  confirm.require({
    header: 'Backup',
    message:
      'Your data is only stored in your browser. Make a backup to avoid losing it.',
    acceptProps: {
      label: 'Create a backup',
    },
    rejectProps: {
      label: 'Cancel',
      severity: 'secondary',
    },
    accept: async () => {
      try {
        await notebooksStore.createBackup(name)
      } catch (e: any) {
        toast.add({
          severity: 'error',
          summary: 'Error',
          detail: e?.message || 'Failed to create a backup',
          life: 2000,
        })
      }
    },
  })
}
</script>

<style scoped>
.buttons {
  display: flex;
  align-items: center;
  gap: 10px;
}
</style>
