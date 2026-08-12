<template>
  <div
    class="flex h-full min-h-0 items-start justify-center overflow-y-auto rounded-lg border border-dashed border-surface-300 p-6 dark:border-surface-600"
  >
    <div class="flex w-full max-w-2xl flex-col gap-5 py-6">
      <header class="flex flex-col gap-1">
        <h3 class="text-lg font-medium">An empty flow</h3>
        <p class="text-sm text-muted-color">
          no cells on <code class="font-mono">main</code> yet — four ways in
        </p>
      </header>

      <div class="grid gap-3 sm:grid-cols-2">
        <PairPanel />

        <div
          class="flex flex-col gap-3 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
        >
          <h4 class="flex items-center gap-2 text-sm font-medium">
            <FilePlus2 :size="15" class="text-muted-color" />
            Create the first cell
          </h4>
          <CopyField value="lumlflow cells new load_data" />
          <p class="text-xs text-muted-color">
            scaffolds a real file under <code class="font-mono">cells/</code> — edit it here or in
            your editor
          </p>
        </div>

        <div
          class="flex flex-col gap-3 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
        >
          <h4 class="flex items-center gap-2 text-sm font-medium">
            <BookOpen :size="15" class="text-muted-color" />
            Read the DSL cheatsheet
          </h4>
          <button
            type="button"
            class="inline-flex items-center gap-1.5 self-start text-sm text-primary hover:underline"
            @click="emit('cheatsheet')"
          >
            open <code class="font-mono text-[13px]">AGENTS.md</code>
            <ArrowRight :size="13" />
          </button>
          <p class="text-xs text-muted-color">
            generated at init — the cell grammar, the four declared types, and the reference syntax
          </p>
        </div>

        <div
          class="flex flex-col gap-2 rounded-lg border border-surface-200 bg-surface-0 p-4 dark:border-surface-700 dark:bg-surface-900"
        >
          <h4 class="flex items-center gap-2 text-sm font-medium">
            <MessageSquareText :size="15" class="text-muted-color" />
            Or just tell the agent what to build
          </h4>
          <p class="text-xs text-muted-color">
            the honest fourth door: once paired, the agent writes the cells and this canvas fills in
            as the journal streams them
          </p>
        </div>
      </div>

      <p class="text-xs text-muted-color">
        assets can also be added from the
        <button
          type="button"
          class="underline underline-offset-2 hover:text-surface-700 dark:hover:text-surface-200"
          @click="emit('notebook')"
        >
          notebook view</button
        >.
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ArrowRight, BookOpen, FilePlus2, MessageSquareText } from 'lucide-vue-next'
import PairPanel from '../components/session/PairPanel.vue'
import CopyField from '../ui/CopyField.vue'

// The empty canvas is doors, not a void: pair, scaffold, read, or delegate.
const emit = defineEmits<{
  cheatsheet: []
  notebook: []
}>()
</script>
