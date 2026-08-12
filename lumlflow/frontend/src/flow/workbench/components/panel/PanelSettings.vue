<template>
  <section class="flex flex-col gap-3 min-w-0">
    <SectionLabel label="settings" />

    <div class="flex flex-col gap-1.5 px-1.5">
      <p class="text-xs font-medium">reactivity</p>
      <SelectButton
        :model-value="settings.reactivity"
        :options="reactivityOptions"
        option-label="label"
        option-value="value"
        :allow-empty="false"
        size="small"
        :pt="smallOptions"
        @update:model-value="setReactivity"
      />
      <div v-if="settings.reactivity === 'auto'" class="flex items-center gap-2 text-xs">
        <span class="text-muted-color">auto below</span>
        <InputNumber
          :model-value="settings.autoThresholdSeconds"
          :min="1"
          :max="3600"
          suffix="s"
          size="small"
          :input-style="{ width: '4.5rem' }"
          @update:model-value="setThreshold"
        />
        <span class="text-muted-color">recorded cost</span>
      </div>
      <p class="text-[11px] text-muted-color">
        lazy marks and waits; auto materializes below the threshold. Per-asset eager lives on the
        card.
      </p>
    </div>

    <div class="flex flex-col gap-1.5 px-1.5">
      <p class="text-xs font-medium">on env change</p>
      <Select
        :model-value="settings.onEnvChange"
        :options="envChangeOptions"
        option-label="label"
        option-value="value"
        size="small"
        class="w-full"
        @update:model-value="setEnvPolicy"
      />
      <p class="text-[11px] text-muted-color">
        flow-local shared code always hot-reloads — that is a correctness rule, not a setting
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import { InputNumber, Select, SelectButton } from 'primevue'
import type { FlowSettings } from '../../model/types'
import SectionLabel from '../../ui/SectionLabel.vue'

/**
 * The two settings that are real. Reactivity is lazy / auto-below-threshold
 * (the third state, eager, is per-asset and lives on the card); the env-change
 * policy governs third-party packages only.
 */
const props = defineProps<{ settings: FlowSettings }>()

const emit = defineEmits<{ update: [settings: FlowSettings] }>()

const reactivityOptions = [
  { label: 'lazy', value: 'lazy' },
  { label: 'auto below threshold', value: 'auto' },
]

const envChangeOptions = [
  { label: 'ask to restart', value: 'ask' },
  { label: 'restart automatically', value: 'restart' },
  { label: 'never', value: 'never' },
]

const smallOptions = { pcToggleButton: { root: { class: 'text-xs' } } }

function setReactivity(value: FlowSettings['reactivity']): void {
  emit('update', { ...props.settings, reactivity: value })
}

function setThreshold(value: number | null): void {
  if (value !== null) emit('update', { ...props.settings, autoThresholdSeconds: value })
}

function setEnvPolicy(value: FlowSettings['onEnvChange']): void {
  emit('update', { ...props.settings, onEnvChange: value })
}
</script>
