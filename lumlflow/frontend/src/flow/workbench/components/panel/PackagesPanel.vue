<template>
  <section class="flex flex-col gap-1.5 min-w-0">
    <SectionLabel label="packages" :count="env.packages.length" />
    <EnvMismatchBanner v-if="env.mismatch" />
    <ul class="flex flex-col">
      <li
        v-for="pkg in env.packages"
        :key="pkg.name"
        class="flex items-center gap-2 px-1.5 py-1 min-w-0"
      >
        <span class="font-mono text-[13px] truncate">{{ pkg.name }}</span>
        <Tag
          v-if="pkg.pendingRestart"
          v-tooltip.top="'Installed into the env but not yet active in the running kernel'"
          value="restart kernel to apply"
          severity="warn"
          :pt="tinyTag"
        />
        <span class="ml-auto shrink-0 font-mono text-[11px] text-muted-color">
          {{ pkg.version }}
        </span>
      </li>
    </ul>
    <p class="text-[11px] text-muted-color px-1.5">
      python {{ env.pythonVersion }} · resolved from uv.lock — the CLI stays primary for add/remove
    </p>
  </section>
</template>

<script setup lang="ts">
import { Tag } from 'primevue'
import type { EnvState } from '../../model/types'
import SectionLabel from '../../ui/SectionLabel.vue'
import EnvMismatchBanner from '../session/EnvMismatchBanner.vue'

defineProps<{ env: EnvState }>()

const tinyTag = { root: { class: 'text-[10px] font-normal px-1.5 py-0 shrink-0' } }
</script>
