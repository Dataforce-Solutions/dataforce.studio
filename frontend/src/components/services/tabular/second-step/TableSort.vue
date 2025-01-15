<template>
  <d-overlay-badge v-if="multiSortMeta.length" :value="multiSortMeta.length">
    <d-button severity="secondary" rounded variant="outlined" @click="toggleSort">
      <span class="fz-14 fw-500">Sort</span>
      <ArrowDownUp width="14" height="14" />
    </d-button>
  </d-overlay-badge>
  <d-button v-else severity="secondary" rounded variant="outlined" @click="toggleSort">
    <span class="fz-14 fw-500">Sort</span>
    <ArrowDownUp width="14" height="14" />
  </d-button>
  <d-popover ref="sortPopover">
    <div class="popover-wrapper" :style="{ width: '36.8rem' }">
      <div class="sort-list">
        <div v-for="sortItem in sortData" :key="sortItem.id" class="sort-item">
          <d-select
            :options="columnsForSelect"
            v-model="sortItem.selectedColumn"
            :optionDisabled="(option: string) => isOptionDisabled(option, sortItem.id)"
          />
          <div class="sort-radio">
            <div class="radio">
              <d-radio-button
                v-model="sortItem.sortOrder"
                :inputId="`sort_${sortItem.id}_1`"
                value="1"
              />
              <label :for="`sort_${sortItem.id}_1`">A -> Z</label>
            </div>
            <div class="radio">
              <d-radio-button
                v-model="sortItem.sortOrder"
                :inputId="`sort_${sortItem.id}_2`"
                value="-1"
              />
              <label :for="`sort_${sortItem.id}_2`">Z -> A</label>
            </div>
          </div>
          <d-button
            v-if="sortData.length > 1"
            severity="secondary"
            variant="outlined"
            @click="deleteSort(sortItem.id)"
          >
            <template #icon>
              <Trash2 width="14" height="14" />
            </template>
          </d-button>
        </div>
      </div>
      <d-divider />
      <div class="popover-footer">
        <d-button label="Add sort" variant="text" @click="addSort">
          <template #icon>
            <Plus width="14" height="14" />
          </template>
        </d-button>
        <div class="popover-footer-buttons">
          <d-button label="clear" severity="secondary" variant="outlined" @click="clear" />
          <d-button
            label="apply"
            severity="secondary"
            :disabled="!isSortAvailable"
            @click="apply"
          />
        </div>
      </div>
    </div>
  </d-popover>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { ArrowDownUp, Trash2, Plus } from 'lucide-vue-next'

type Props = {
  columns: string[]
  multiSortMeta: any[]
}

type Emits = {
  (event: 'update:multiSortMeta', sortMeta: any[]): void
}

type SortItem = {
  id: number
  selectedColumn: string
  sortOrder: 1 | -1 | null
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const sortPopover = ref()
const sortData = ref<SortItem[]>([
  {
    id: 1,
    selectedColumn: props.columns[0],
    sortOrder: null,
  },
])

const isSortAvailable = computed(() => {
  return sortData.value.reduce((acc, item) => {
    if (!item.selectedColumn || !item.sortOrder) acc = false
    return acc
  }, true)
})
const columnsForSelect = computed(() => {
  const columnsForSelect = [...props.columns]

  const selected = sortData.value
    .filter((item) => !columnsForSelect.includes(item.selectedColumn))
    .map((item) => item.selectedColumn)

  columnsForSelect.push(...selected)

  return columnsForSelect
})

function toggleSort(event: any) {
  sortPopover.value.toggle(event)
}
function deleteSort(id: number) {
  sortData.value = sortData.value.filter((item) => item.id !== id)
}
function addSort() {
  const selectedColumnsNames = sortData.value.map((item) => item.selectedColumn)
  const currentColumn = props.columns.find((column) => !selectedColumnsNames.includes(column))
  sortData.value.push({
    id: sortData.value.length + 1,
    selectedColumn: currentColumn || '',
    sortOrder: null,
  })
}
function clear() {
  sortData.value = [
    {
      id: 1,
      selectedColumn: props.columns[0],
      sortOrder: null,
    },
  ]
  emit('update:multiSortMeta', [])
  sortPopover.value.toggle()
}
function apply() {
  if (!isSortAvailable.value) return

  const newMultiSortMeta = sortData.value.map((item) => ({
    field: item.selectedColumn,
    order: item.sortOrder,
  }))
  emit('update:multiSortMeta', JSON.parse(JSON.stringify(newMultiSortMeta)))
  sortPopover.value.toggle()
}
function isOptionDisabled(option: string, id: number) {
  return sortData.value.find((item) => item.selectedColumn === option && item.id !== id)
}
</script>

<style scoped>
.popover-wrapper {
  padding: 1.5rem;
}

.popover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.popover-footer-buttons {
  display: flex;
  gap: 12px;
}

.sort-list {
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.sort-item {
  display: grid;
  gap: 1.5rem;
  grid-template-columns: 1fr auto 35px;
  align-items: center;
}

.sort-radio {
  display: flex;
  align-items: center;
  gap: 1.25rem;
}

.radio {
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
