<template>
  <div>
    <header class="card-header">
      <h3 class="card-title">
        Detailed view
        <info v-if="isTrainMode" width="20" height="20" v-tooltip.bottom="`Warning`" />
      </h3>
      <div class="detailed-actions">
        <!--<div class="highlight-toggle-wrapper">
          <ToggleSwitch v-model="highlightIncorrect" />
          <span>highlight incorrect</span>
        </div>-->
        <d-button variant="text" severity="secondary" @click="maximizeTable = true">
          <template #icon>
            <Maximize2 width="20" height="20" />
          </template>
        </d-button>
      </div>
    </header>
    <DataTable
      v-if="values.length"
      :value="values"
      showGridlines
      stripedRows
      scrollable
      scrollHeight="19rem"
      :virtualScrollerOptions="{ itemSize: 33 }"
      class="table"
    >
      <Column
        v-for="column in currentColumns"
        :id="column"
        :field="column"
        :header="column === '<=PREDICTED=>' ? 'Prediction' : column"
      >
      </Column>
    </DataTable>
    <Dialog
      v-model:visible="maximizeTable"
      blockScroll
      header="Detailed view"
      class="p-dialog-maximized"
      :breakpoints="{ '1199px': '75vw', '575px': '90vw' }"
    >
      <template #header>
        <header
          class="card-header"
          :style="{ width: '100%', marginBottom: '0', marginRight: '20px' }"
        >
          <h3 class="card-title">Detailed view</h3>
          <div class="detailed-actions">
            <!--<div class="highlight-toggle-wrapper">
              <ToggleSwitch v-model="highlightIncorrect" />
              <span>highlight incorrect</span>
            </div>-->
          </div>
        </header>
      </template>
      <template #closeicon>
        <Minimize2 />
      </template>
      <DataTable
        v-if="values.length"
        :value="values"
        showGridlines
        stripedRows
        scrollable
        scrollHeight="calc(100vh - 120px)"
        :virtualScrollerOptions="{ itemSize: 46 }"
        class="table"
      >
        <Column
          v-for="column in currentColumns"
          :id="column"
          :field="column"
          :header="column === '<=PREDICTED=>' ? 'Prediction' : column"
        >
        </Column>
      </DataTable>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { ToggleSwitch, DataTable, Column, Dialog } from 'primevue'

import { Maximize2, Minimize2, Info } from 'lucide-vue-next'

type Props = {
  values: object[]
  isTrainMode: boolean
}

const props = defineProps<Props>()

// const highlightIncorrect = ref(false)
const maximizeTable = ref(false)

const currentColumns = computed(() => Object.keys(props.values[0]))
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.card-title {
  font-size: 1.5rem;
}

.detailed-actions {
  display: flex;
  align-items: center;
  gap: 24px;
}

/* .highlight-toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--p-primary-color);
} */

.table {
  font-size: 14px;
}
</style>
