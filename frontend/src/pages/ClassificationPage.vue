<template>
  <tabular-wrapper :steps="steps"></tabular-wrapper>
</template>

<script setup lang="ts">
import TabularWrapper from '@/components/services/tabular/TabularWrapper.vue'

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
