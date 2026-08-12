<template>
  <div class="flex max-w-3xl flex-col gap-8 pb-12">
    <header>
      <h3 class="text-xl font-medium">Flows</h3>
      <p class="mt-1 text-sm text-muted-color">
        The flows the daemon knows on this machine. Opening one lands on its workbench.
      </p>
    </header>

    <div
      class="rounded-lg border border-surface-200 bg-surface-0 divide-y divide-surface-200 dark:divide-surface-700 dark:border-surface-700 dark:bg-surface-900"
    >
      <component
        :is="isOpenable(entry) ? RouterLink : 'button'"
        v-for="entry in knownFlows"
        :key="entry.name"
        v-bind="isOpenable(entry) ? { to: '/flow/work' } : { type: 'button' }"
        class="flex w-full flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 text-left transition-colors hover:bg-surface-50 dark:hover:bg-surface-800"
        @click="onOpen(entry)"
      >
        <span class="w-40 shrink-0">
          <FlowStateDot :state="entry.state" />
        </span>
        <span class="flex min-w-0 flex-1 flex-col">
          <span class="truncate font-mono text-sm">{{ entry.name }}</span>
          <span class="truncate text-xs text-muted-color">{{ entry.path }}</span>
        </span>
        <ActorChip
          v-if="entry.pairedAgent"
          :actor="{ kind: 'agent', label: entry.pairedAgent }"
          muted
        />
        <span class="whitespace-nowrap text-xs text-muted-color">
          {{ formatCount(entry.branchCount, 'branch') }} ·
          {{ formatCount(entry.cellCount, 'cell') }}
        </span>
        <span class="w-16 whitespace-nowrap text-right text-xs text-muted-color">
          {{ entry.diskUsage }}
        </span>
        <span class="w-20 whitespace-nowrap text-right text-xs text-muted-color">
          {{ entry.lastOpened }}
        </span>
      </component>
    </div>

    <div class="flex flex-col gap-3">
      <SectionLabel label="Open or create" />
      <div class="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          class="flex flex-col items-start gap-1 rounded-lg border border-dashed border-surface-300 p-3 text-left transition-colors hover:border-surface-400 dark:border-surface-600 dark:hover:border-surface-500"
          @click="fixtureOnly('Open a folder')"
        >
          <span class="inline-flex items-center gap-2 text-sm">
            <FolderOpen :size="15" class="text-muted-color" />
            Open a folder…
          </span>
          <span class="text-xs text-muted-color">
            Point the daemon at an existing flow directory.
          </span>
        </button>

        <div
          class="flex flex-col gap-2 rounded-lg border border-dashed border-surface-300 p-3 dark:border-surface-600"
        >
          <span class="inline-flex items-center gap-2 text-sm">
            <FilePlus2 :size="15" class="text-muted-color" />
            Init a flow here
          </span>
          <CopyField value="lumlflow init" />
          <p class="text-xs text-muted-color">
            Scaffolds <code class="font-mono">cells/</code>,
            <code class="font-mono">flow.yaml</code>, <code class="font-mono">pyproject.toml</code>,
            <code class="font-mono">AGENTS.md</code>, and the store.
          </p>
        </div>
      </div>
      <button
        type="button"
        class="inline-flex items-center gap-1.5 self-start text-xs text-muted-color hover:underline"
        @click="fixtureOnly('DSL cheatsheet')"
      >
        <BookOpen :size="13" />
        read the DSL cheatsheet — <code class="font-mono">AGENTS.md</code>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useToast } from 'primevue/usetoast'
import { RouterLink } from 'vue-router'
import { BookOpen, FilePlus2, FolderOpen } from 'lucide-vue-next'
import { knownFlows, type FlowListEntry } from '../fixtures/flows'
import { formatCount } from '../model/format'
import ActorChip from '../ui/ActorChip.vue'
import CopyField from '../ui/CopyField.vue'
import FlowStateDot from '../ui/FlowStateDot.vue'
import SectionLabel from '../ui/SectionLabel.vue'

const toast = useToast()

// Only the churn fixture has a workbench behind it; the rest are picker dressing.
function isOpenable(entry: FlowListEntry): boolean {
  return entry.name === 'churn.flow'
}

function onOpen(entry: FlowListEntry): void {
  if (!isOpenable(entry)) fixtureOnly(entry.name)
}

function fixtureOnly(what: string): void {
  toast.add({
    severity: 'secondary',
    summary: 'Fixture only',
    detail: `${what} has no surface behind it in this draft — only churn.flow opens the workbench`,
    life: 2500,
  })
}
</script>
