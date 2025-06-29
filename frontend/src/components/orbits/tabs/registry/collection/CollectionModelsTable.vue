<template>
  <div>
    <div class="content">
      <div class="toolbar">
        <div>{{ selectedModels?.length || 0 }} Selected</div>
        <Button
          variant="text"
          severity="secondary"
          :disabled="!selectedModels?.length"
          rounded
          @click="onDeleteClick"
        >
          <template #icon>
            <Trash2 :size="14" />
          </template>
        </Button>
      </div>
      <div class="table-wrapper">
        <DataTable
          v-model:selection="selectedModels"
          :value="tableData"
          :pt="{
            emptyMessageCell: {
              style: 'padding: 25px 16px;',
            },
          }"
          dataKey="id"
          style="min-width: 1560px; font-size: 14px"
        >
          <template #empty>
            <div class="placeholder">No models to show. Add model to the table.</div>
          </template>
          <Column selectionMode="multiple" headerStyle="width: 30px"></Column>
          <Column
            field="modelName"
            header="Model name"
            :bodyStyle="columnBodyStyle + 'width: 180px; max-width: 180px;'"
          >
            <template #body="{ data }">
              <div
                v-tooltip="data.modelName"
                style="display: inline-block; max-width: 180px"
                :style="columnBodyStyle"
              >
                {{ data.modelName }}
              </div>
            </template>
          </Column>
          <Column
            field="createdTime"
            header="Creation time"
            :bodyStyle="columnBodyStyle + 'width: 180px; max-width: 180px;'"
          ></Column>
          <Column
            field="description"
            header="Description"
            bodyStyle="width: 203px; max-width: 203px;"
          >
            <template #body="{ data }">
              <div v-tooltip="data.description" class="description">
                {{ data.description }}
              </div>
            </template></Column
          >
          <Column
            field="status"
            header="Status"
            :bodyStyle="columnBodyStyle + 'width: 203px; max-width: 203px;'"
          >
            <template #body="{ data }">
              <div v-if="data.status === MlModelStatusEnum.deletion_failed">Deletion failed</div>
              <div v-if="data.status === MlModelStatusEnum.pending_deletion">Pending deletion</div>
              <div v-if="data.status === MlModelStatusEnum.pending_upload">Pending upload</div>
              <div v-if="data.status === MlModelStatusEnum.upload_failed">Upload failed</div>
              <div v-if="data.status === MlModelStatusEnum.uploaded">Uploaded</div>
            </template>
          </Column>
          <Column
            field="tags"
            header="Tags"
            :bodyStyle="'width: 203px; max-width: 203px; overflow: hidden;'"
          >
            <template #body="{ data }">
              <div class="tags">
                <Tag v-for="(tag, index) in data.tags" :key="index" class="tag">{{ tag }}</Tag>
              </div>
            </template>
          </Column>
          <Column
            field="size"
            header="Size"
            :bodyStyle="columnBodyStyle + 'width: 100px; max-width: 100px;'"
          ></Column>
          <!--<Column header="Loss" sortable style="width: 100px"></Column>
          <Column header="NTE" sortable style="width: 100px"></Column>
          <Column header="Tokenizer" style="width: 120px"></Column>
          <Column header="Activation" style="width: 120px"></Column>-->
        </DataTable>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button, useToast, Tag, useConfirm } from 'primevue'
import { Trash2 } from 'lucide-vue-next'
import { DataTable, Column } from 'primevue'
import { MlModelStatusEnum } from '@/lib/api/orbit-ml-models/interfaces'
import { computed, onBeforeMount, onUnmounted, ref } from 'vue'
import { useModelsStore } from '@/stores/models'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getSizeText } from '@/helpers/helpers'
import { deleteModelConfirmOptions } from '@/lib/primevue/data/confirm'

const columnBodyStyle = 'white-space: nowrap; overflow:hidden; text-overflow: ellipsis;'

const modelsStore = useModelsStore()
const toast = useToast()
const confirm = useConfirm()

const selectedModels = ref([])
const loading = ref(false)

const tableData = computed(() =>
  modelsStore.modelsList.map((item) => ({
    id: item.id,
    modelName: item.file_name,
    createdTime: new Date(item.created_at).toLocaleString(),
    description: item.description,
    tags: item.tags,
    size: getSizeText(item.size),
    status: item.status,
  })),
)

async function confirmDelete() {
  const modelsForDelete = selectedModels.value.map((model: any) => model.id)
  loading.value = true
  try {
    const result = await modelsStore.deleteModels(modelsForDelete)
    if (result.deleted?.length) {
      toast.add(
        simpleSuccessToast(
          `Models: ${result.deleted} has been removed from the collection successfully`,
        ),
      )
    }
    if (result.failed?.length) {
      toast.add(simpleErrorToast(`Failed to delete the models: ${result.failed}`))
    }
  } catch {
    toast.add(simpleErrorToast('Failed to delete models'))
  } finally {
    selectedModels.value = []
    loading.value = false
  }
}

async function onDeleteClick() {
  if (!selectedModels.value?.length || loading.value) return
  confirm.require(deleteModelConfirmOptions(confirmDelete, selectedModels.value?.length))
}

onBeforeMount(async () => {
  try {
    await modelsStore.loadModelsList()
  } catch {
    toast.add(simpleErrorToast('Failed to load models'))
  }
})

onUnmounted(() => {
  modelsStore.resetList()
})
</script>

<style scoped>
.content {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  font-weight: 500;
  margin-bottom: 10px;
}

.table-wrapper {
  overflow: auto;
  max-height: calc(100vh - 330px);
}

.tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
.tag {
  font-weight: 400;
}

.description {
  max-width: 203px;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

@media (min-width: 768px) {
  .content {
    margin: 0 -88px;
  }
}
</style>
