<template>
  <pre class="text-xs font-mono overflow-auto">{{ preview }}</pre>
</template>

<script setup lang="ts">
import type { PreviewValue } from '../model/types'

/**
 * Dispatches a stored preview to the renderer registered for its kind.
 * Renderers are display-only: no emits; links out (tracker refs) render as
 * plain anchors. `density` lets a renderer tighten itself for canvas cards
 * vs. the notebook column vs. the expand drawer.
 */
defineProps<{
  preview: PreviewValue
  density?: 'canvas' | 'notebook' | 'drawer'
}>()
</script>
