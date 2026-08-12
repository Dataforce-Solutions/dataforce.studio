<template>
  <div class="flex flex-col items-center justify-center gap-2 py-8 px-4 text-muted-color">
    <component :is="icon" :size="20" :class="state === 'loading' ? 'animate-spin' : ''" />
    <p class="text-sm">{{ message }}</p>
    <p v-if="detail" class="text-xs opacity-75 font-mono">{{ detail }}</p>
  </div>
</template>

<script lang="ts">
/** Mirrors the @luml/attachments preview-state vocabulary. */
export type PreviewShellState = 'loading' | 'empty' | 'too-big' | 'error' | 'unsupported'
</script>

<script setup lang="ts">
import { computed } from 'vue'
import {
  CircleSlash2,
  FileQuestion,
  FileWarning,
  LoaderCircle,
  TriangleAlert,
  type LucideIcon,
} from 'lucide-vue-next'

const props = defineProps<{
  state: PreviewShellState
  detail?: string
}>()

const CONFIG: Record<PreviewShellState, { icon: LucideIcon; message: string }> = {
  loading: { icon: LoaderCircle, message: 'Loading preview…' },
  empty: { icon: CircleSlash2, message: 'Value is empty' },
  'too-big': { icon: FileWarning, message: 'Too large for preview' },
  unsupported: { icon: FileQuestion, message: 'Not supported for preview' },
  error: { icon: TriangleAlert, message: 'Failed to load preview' },
}

const icon = computed(() => CONFIG[props.state].icon)
const message = computed(() => CONFIG[props.state].message)
</script>
