<template>
  <tabular-wrapper :steps="steps" :task="Tasks.TABULAR_REGRESSION"></tabular-wrapper>
</template>

<script setup lang="ts">
import TabularWrapper from '@/components/services/tabular/TabularWrapper.vue'
import { Tasks } from '@/lib/data-processing/interfaces'

const steps = [
  {
    id: 1,
    text: 'Upload',
  },
  {
    id: 2,
    text: 'Customise',
  },
  {
    id: 3,
    text: 'Evaluate',
  },
]
</script>

<style scoped></style>
