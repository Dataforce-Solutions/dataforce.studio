<template>
  <div class="flex items-center gap-2 text-xs uppercase tracking-wide text-muted-color">
    <span>{{ label }}</span>
    <span v-if="count !== undefined" class="font-normal normal-case">{{ count }}</span>
    <span class="flex-1 border-t border-surface-200 dark:border-surface-700" />
  </div>
</template>

<script setup lang="ts">
defineProps<{ label: string; count?: number }>()
</script>
