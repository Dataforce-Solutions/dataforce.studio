<template>
  <Handle type="target" :position="Position.Top" class="opacity-0" />
  <AssetCard
    :session="data.session"
    :version="data.version"
    :cause="data.cause"
    :selected="data.selected"
    :dimmed="data.dimmed"
    :phase="data.phase"
    @expand="data.onExpand()"
  />
  <Handle type="source" :position="Position.Bottom" class="opacity-0" />
</template>

<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import AssetCard from './AssetCard.vue'
import type { AssetVersion, FlowSession, UnsyncedCause } from '../../types'

export interface AssetNodeData {
  session: FlowSession
  version: AssetVersion
  cause: UnsyncedCause | null
  selected: boolean
  dimmed: boolean
  phase: string | null
  onExpand: () => void
}

defineProps<{ data: AssetNodeData }>()
</script>
