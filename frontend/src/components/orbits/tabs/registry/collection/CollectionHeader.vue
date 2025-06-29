<template>
  <header class="header">
    <h3 class="title">{{ title }}</h3>
    <Button @click="$emit('add')">
      <Plus :size="14" />
      <span>Add model</span>
    </Button>
  </header>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'

type Props = {
  title: string
}

type Emits = {
  add: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 32px 0;
}
</style>
