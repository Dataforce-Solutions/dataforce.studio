<template>
  <div>
    <header class="card-header">
      <h3 class="card-title">Detailed view</h3>
      <div class="detailed-actions">
        <div class="highlight-toggle-wrapper">
          <ToggleSwitch v-model="highlightIncorrect" />
          <span>highlight incorrect</span>
        </div>
        <d-button variant="text" severity="secondary" @click="maximizeTable = true">
          <template #icon>
            <Maximize2 width="20" height="20" />
          </template>
        </d-button>
      </div>
    </header>
    <DataTable :value="mockTable.filter((item, index) => index < 6)" showGridlines stripedRows>
      <Column field="id" header="AppointmentId" />
      <Column field="date" header="AppointmentDate" />
      <Column field="time" header="AppointmentTime" />
      <Column field="prediction" header="Prediction" />
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
            <div class="highlight-toggle-wrapper">
              <ToggleSwitch v-model="highlightIncorrect" />
              <span>highlight incorrect</span>
            </div>
          </div>
        </header>
      </template>
      <template #closeicon>
        <Minimize2 />
      </template>
      <DataTable :value="mockTable" showGridlines stripedRows>
        <Column field="id" header="AppointmentId" />
        <Column field="date" header="AppointmentDate" />
        <Column field="time" header="AppointmentTime" />
        <Column field="prediction" header="Prediction" />
      </DataTable>
    </Dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'

import { ToggleSwitch, DataTable, Column, Dialog } from 'primevue'

import { Maximize2, Minimize2 } from 'lucide-vue-next'

const mockTable = [
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
  {
    id: 5.1,
    date: 3.5,
    time: 1.4,
    prediction: 'setosa',
  },
]

const highlightIncorrect = ref(false)
const maximizeTable = ref(false)
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

.highlight-toggle-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  color: var(--p-primary-color);
}
</style>
