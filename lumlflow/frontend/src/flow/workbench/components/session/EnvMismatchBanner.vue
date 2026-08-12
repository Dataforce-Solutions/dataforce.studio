<template>
  <div
    class="flex flex-col gap-2 rounded-lg border border-amber-200 bg-amber-50 dark:border-amber-500/30 dark:bg-amber-500/10 p-3"
  >
    <div class="flex items-start gap-2 text-sm">
      <PackageX :size="15" class="shrink-0 mt-0.5 text-amber-600 dark:text-amber-400" />
      <p class="min-w-0 text-amber-700 dark:text-amber-300">
        <span class="font-medium">env mismatch</span>
        — restart the kernel under this branch's lock
      </p>
    </div>
    <p class="text-xs text-amber-700/80 dark:text-amber-300/80 pl-6">
      background work for this branch is deferred meanwhile
    </p>
    <div class="pl-6">
      <Button label="Restart kernel" size="small" severity="warn" outlined @click="emit('restart')">
        <template #icon>
          <RotateCcw :size="13" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { PackageX, RotateCcw } from 'lucide-vue-next'

// The branch's lockfile differs from the live venv. The UI says work is
// deferred rather than letting the branch look idle for no visible reason.
const emit = defineEmits<{ restart: [] }>()
</script>
