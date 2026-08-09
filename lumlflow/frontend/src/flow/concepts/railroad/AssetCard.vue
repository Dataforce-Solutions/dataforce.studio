<template>
  <Card
    class="w-full h-full transition-shadow"
    :class="[
      selected ? 'ring-2 ring-primary-500' : '',
      dimmed ? 'opacity-40' : '',
      phase === 'invalidating' ? 'rr-invalidating' : '',
    ]"
    :pt="cardPt"
  >
    <template #title>
      <div class="flex items-start gap-3">
        <component :is="kindIcon" :size="20" class="mt-1 shrink-0 text-muted-color" />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-2 flex-wrap">
            <h3 class="text-lg font-medium truncate">{{ version.definition.name }}</h3>
            <Tag :value="version.definition.kind" severity="secondary" />
            <Tag v-if="cause" :value="causeLabel" :severity="causeSeverity" />
            <Tag v-if="version.status === 'failed'" value="failed" severity="danger" />
          </div>
          <p class="text-sm text-muted-color mt-1 font-normal">{{ version.definition.doc }}</p>
        </div>
        <Button
          v-tooltip.left="'Open full size'"
          icon="pi"
          text
          rounded
          severity="secondary"
          aria-label="Open full size"
          @click.stop="emit('expand')"
        >
          <template #icon><Maximize2 :size="18" /></template>
        </Button>
      </div>
    </template>

    <template #content>
      <div class="flex flex-col gap-4">
        <div
          v-if="primaryValue"
          class="rounded-md border border-surface-200 dark:border-surface-700 p-4 overflow-auto"
          :style="{ maxHeight: `${artifactHeight}px` }"
        >
          <ArtifactView :value="primaryValue" />
        </div>
        <Message v-else-if="version.status === 'failed'" severity="error" :closable="false">
          {{ version.failureMessage }}
        </Message>
        <Message v-else severity="secondary" :closable="false">
          Not materialized in this branch.
        </Message>

        <div class="flex items-center gap-3 flex-wrap text-sm">
          <span class="flex items-center gap-1.5 text-muted-color">
            <span
              class="w-2 h-2 rounded-full"
              :style="{ background: session.agents[version.authoredBy]?.color }"
            />
            {{ session.agents[version.authoredBy]?.label ?? version.authoredBy }}
          </span>
          <span class="text-muted-color">·</span>
          <span class="text-muted-color truncate flex-1 min-w-32">{{ version.intent }}</span>
          <Tag :value="formatCost(materialization?.costSeconds ?? 0)" severity="secondary" />
        </div>

        <div v-if="version.definition.deps.length" class="text-sm text-muted-color">
          reads
          <span v-for="(dep, index) in depNames" :key="dep">
            <span class="text-color">{{ dep }}</span
            ><span v-if="index < depNames.length - 1">, </span>
          </span>
        </div>

        <Accordion :value="showSource ? '0' : undefined">
          <AccordionPanel value="0">
            <AccordionHeader>Source</AccordionHeader>
            <AccordionContent>
              <pre
                class="text-xs overflow-x-auto font-mono leading-relaxed"
              >{{ version.definition.source }}</pre>
            </AccordionContent>
          </AccordionPanel>
        </Accordion>
      </div>
    </template>
  </Card>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionPanel,
  Button,
  Card,
  Message,
  Tag,
  type CardPassThroughOptions,
} from 'primevue'
import {
  Box,
  Database,
  FileText,
  FlaskConical,
  Gauge,
  LineChart,
  Maximize2,
  Table2,
} from 'lucide-vue-next'
import ArtifactView from '../../components/ArtifactView.vue'
import { formatCost } from '../../engine'
import type { ArtifactValue, AssetVersion, FlowSession, UnsyncedCause } from '../../types'

/**
 * One asset, rendered output-first.
 *
 * The materialization is the card's body, not something behind a click — in
 * DS/ML the artifact of record is the finding, and the code is scaffolding.
 * That is the product's first design pillar, and burying the output in a
 * sidebar made the workbench read as a pipeline rather than a notebook.
 */
const props = defineProps<{
  session: FlowSession
  version: AssetVersion
  cause: UnsyncedCause | null
  selected?: boolean
  dimmed?: boolean
  phase?: string | null
  artifactHeight?: number
  showSource?: boolean
}>()

const emit = defineEmits<{ expand: [] }>()

const artifactHeight = computed(() => props.artifactHeight ?? 260)

const cardPt: CardPassThroughOptions = {
  body: { class: 'gap-4' },
  content: { class: 'pt-0' },
}

const materialization = computed(() => props.session.materializations[props.version.versionId])

const primaryValue = computed<ArtifactValue | null>(() => {
  const values = Object.values(materialization.value?.values ?? {})
  return (values[0] as ArtifactValue | undefined) ?? null
})

const depNames = computed(() =>
  props.version.definition.deps.map(
    (depId) => props.session.assets[depId]?.at(-1)?.definition.name ?? depId,
  ),
)

const kindIcon = computed(() => {
  switch (props.version.definition.kind) {
    case 'source':
      return Database
    case 'frame':
      return Table2
    case 'plot':
      return LineChart
    case 'note':
      return FileText
    case 'model':
      return Box
    case 'experiment':
      return FlaskConical
    default:
      return Gauge
  }
})

const causeLabel = computed(() => {
  switch (props.cause) {
    case 'definition-changed':
      return 'changed here'
    case 'deps-rewired':
      return 'rewired here'
    default:
      return 'rematerialized'
  }
})

// Only an edit is worth an alarm colour. Downstream assets whose inputs merely
// moved are the majority below any change, and colouring them the same way
// turns one edit into a screen full of equally urgent warnings.
const causeSeverity = computed(() =>
  props.cause === 'parent-rematerialized' ? 'secondary' : 'warn',
)
</script>

<style scoped>
@keyframes rr-desaturate {
  0% { filter: none; }
  50% { filter: saturate(0.2) brightness(0.98); }
  100% { filter: none; }
}

.rr-invalidating {
  animation: rr-desaturate 900ms ease-in-out;
}

@media (prefers-reduced-motion: reduce) {
  .rr-invalidating {
    animation: none;
  }
}
</style>
