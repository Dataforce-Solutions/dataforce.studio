<template>
  <UiDialogRight v-model:visible="visible" :icon="Info" title="Artifact details" max-width="420px">
    <div v-if="data?.data" class="details">
      <div class="details__heading">
        <Tag :severity="typeConfig.severity" class="details__type">
          <component :is="typeConfig.icon" :size="14" />
          {{ typeConfig.text }}
        </Tag>
        <h3 class="details__name">{{ data.title }}</h3>
      </div>

      <dl class="details__properties">
        <div class="details__property">
          <dt>Collection</dt>
          <dd>{{ data.collectionName ?? 'Unknown collection' }}</dd>
        </div>
        <div class="details__property">
          <dt>Created</dt>
          <dd>{{ createdAt }}</dd>
        </div>
        <div class="details__property">
          <dt>Status</dt>
          <dd>
            <Tag :severity="statusConfig.severity">{{ statusConfig.text }}</Tag>
          </dd>
        </div>
      </dl>
    </div>

    <template #footer>
      <div v-if="artifactRoute" class="details__actions">
        <RouterLink :to="artifactRoute" class="details__link">
          <ExternalLink :size="14" />
          Open artifact
        </RouterLink>
        <RouterLink
          v-if="data?.variant !== 'main' && lineageRoute"
          :to="lineageRoute"
          class="details__link"
        >
          <Workflow :size="14" />
          Focus lineage
        </RouterLink>
      </div>
    </template>
  </UiDialogRight>
</template>

<script setup lang="ts">
import type { LineageNodeData } from './lineage.interface'
import {
  ARTIFACT_TYPE_TAGS_CONFIG,
  STATUS_TAGS_CONFIG,
} from '@/components/orbits/tabs/registry/collection/artifacts-table/models-table.data'
import UiDialogRight from '@/components/ui/dialogs/UiDialogRight.vue'
import { ExternalLink, Info, Workflow } from 'lucide-vue-next'
import { Tag } from 'primevue'
import { computed } from 'vue'
import { useRoute, type RouteLocationRaw } from 'vue-router'

interface Props {
  data: LineageNodeData | null
}

const props = defineProps<Props>()
const visible = defineModel<boolean>('visible', { default: false })
const route = useRoute()

const typeConfig = computed(() => {
  if (!props.data) throw new Error('Artifact details are not available')
  return ARTIFACT_TYPE_TAGS_CONFIG[props.data.type]
})

const statusConfig = computed(() => {
  if (!props.data?.data) throw new Error('Artifact status is not available')
  return STATUS_TAGS_CONFIG[props.data.data.status]
})

const createdAt = computed(() => {
  if (!props.data?.data) return ''
  return new Date(props.data.data.created_at).toLocaleString()
})

function artifactLocation(name: 'artifact' | 'lineage'): RouteLocationRaw | null {
  if (!props.data?.artifactId || !props.data.collectionId) return null
  return {
    name,
    params: {
      organizationId: route.params.organizationId,
      id: route.params.id,
      collectionId: props.data.collectionId,
      artifactId: props.data.artifactId,
    },
  }
}

const artifactRoute = computed(() => artifactLocation('artifact'))
const lineageRoute = computed(() => artifactLocation('lineage'))
</script>

<style scoped>
.details {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.details__heading {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 10px;
}

.details__type {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.details__name {
  margin: 0;
  font-size: 20px;
  font-weight: 500;
  overflow-wrap: anywhere;
}

.details__properties {
  margin: 0;
}

.details__property {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 20px;
  padding: 10px 0;
  border-bottom: 1px solid var(--p-content-border-color);
  font-size: 14px;
}

.details__property dt {
  color: var(--p-text-muted-color);
}

.details__property dd {
  margin: 0;
  text-align: right;
}

.details__actions {
  display: flex;
  width: 100%;
  justify-content: flex-end;
  gap: 12px;
}

.details__link {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 7px;
  padding: 8px 14px;
  border: 1px solid var(--p-button-secondary-border-color);
  border-radius: var(--p-button-border-radius);
  color: var(--p-button-secondary-color);
  background: var(--p-button-secondary-background);
  text-decoration: none;
  font-size: 14px;
}

.details__link:hover {
  background: var(--p-button-secondary-hover-background);
}
</style>
