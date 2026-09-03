<template>
  <div class="buttons">
    <div class="depth-control">
      <label for="lineage-depth">Depth</label>
      <Select
        input-id="lineage-depth"
        :model-value="lineageStore.depth"
        :options="DEPTH_OPTIONS"
        :disabled="lineageStore.isLoading"
        class="depth-select"
        @update:model-value="onDepthChange"
      />
    </div>
    <Button
      severity="secondary"
      class="light-button"
      :disabled="!lineageStore.hasNodes || lineageStore.isLoading"
      @click="resetPositions"
    >
      Reset positions <RotateCcw :size="14" />
    </Button>
    <Button severity="secondary" class="light-button" @click="toggleMaximized">
      <template #icon>
        <component :is="scaleIcon" :size="14" />
      </template>
    </Button>
  </div>
</template>

<script setup lang="ts">
import { Maximize2, Minimize2, RotateCcw } from 'lucide-vue-next'
import { Button, Select } from 'primevue'
import { computed } from 'vue'
import { useLineageStore } from '@/stores/lineage'

const lineageStore = useLineageStore()
const emit = defineEmits<{ depthChange: [depth: number] }>()

const isMaximized = defineModel('isMaximized', { default: false })
const DEPTH_OPTIONS = [1, 2, 3, 4, 5]

const scaleIcon = computed(() => {
  return isMaximized.value ? Minimize2 : Maximize2
})

function toggleMaximized() {
  isMaximized.value = !isMaximized.value
}

function resetPositions() {
  lineageStore.resetPositions()
}

function onDepthChange(value: number): void {
  emit('depthChange', value)
}
</script>

<style scoped>
.light-button {
  background-color: var(--p-card-background) !important;
  border-color: transparent;
  box-shadow: var(--card-shadow);
}
.buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}
.depth-control {
  display: flex;
  align-items: center;
  gap: 7px;
  padding: 4px 8px;
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  font-size: 13px;
}
.depth-select {
  width: 64px;
}
</style>
