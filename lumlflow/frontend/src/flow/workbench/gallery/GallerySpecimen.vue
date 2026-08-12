<template>
  <section class="flex flex-col gap-2 min-w-0">
    <div class="flex items-baseline gap-3">
      <h4 class="text-sm font-medium">{{ title }}</h4>
      <p v-if="caption" class="text-xs text-muted-color">{{ caption }}</p>
    </div>
    <div
      class="rounded-lg border border-surface-200 dark:border-surface-700 bg-surface-0 dark:bg-surface-900 p-4 overflow-x-auto"
      :class="[padded === false ? 'p-0!' : '', grow ? 'flex-1' : '']"
    >
      <slot />
    </div>
  </section>
</template>

<script setup lang="ts">
/** Uniform exhibit frame — every gallery section presents specimens through this. */
defineProps<{
  title: string
  caption?: string
  padded?: boolean
  grow?: boolean
}>()
</script>
