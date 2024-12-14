<template>
  <service-wrapper :steps="steps"></service-wrapper>
</template>

<script setup lang="ts">
import ServiceWrapper from '@/components/services/ServiceWrapper.vue'

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
