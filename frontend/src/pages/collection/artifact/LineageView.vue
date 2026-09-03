<template>
  <div ref="viewRef" class="view">
    <LineageWrapper v-model:is-maximized="isMaximized" @depth-change="onDepthChange" />
  </div>

  <Teleport to="body">
    <Transition name="backdrop">
      <div v-if="isMaximized" class="backdrop" @click="isMaximized = false" />
    </Transition>
  </Teleport>

  <LinkCreator />
  <ReplaceArtifactModal />

  <LineageArtifactDetails
    :visible="!!lineageStore.detailedArtifact"
    :data="lineageStore.detailedArtifact"
    @update:visible="onDetailsVisibilityChange"
  />
</template>

<script setup lang="ts">
import { useLineageStore } from '@/stores/lineage'
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { onBeforeRouteLeave, onBeforeRouteUpdate, useRoute } from 'vue-router'
import { useConfirm, useToast } from 'primevue'
import { discardLineageChangesConfirmOptions } from '@/lib/primevue/data/confirm'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { useArtifactsStore } from '@/stores/artifacts'
import LineageWrapper from '@/components/lineage/LineageWrapper.vue'
import LinkCreator from '@/components/lineage/LinkCreator.vue'
import ReplaceArtifactModal from '@/components/lineage/ReplaceArtifactModal.vue'
import LineageArtifactDetails from '@/components/lineage/LineageArtifactDetails.vue'

const lineageStore = useLineageStore()
const artifactsStore = useArtifactsStore()
const route = useRoute()
const confirm = useConfirm()
const toast = useToast()

const isMaximized = ref(false)
const viewRef = ref<HTMLElement | null>(null)
const savedRect = ref<DOMRect | null>(null)

const DURATION = 350
const EASING = 'cubic-bezier(0.4, 0, 0.2, 1)'
const GAP = 24
const RADIUS = '12px'

const TRANSITION = ['top', 'left', 'width', 'height', 'border-radius']
  .map((p) => `${p} ${DURATION}ms ${EASING}`)
  .join(', ')

watch(isMaximized, (maximized) => {
  const el = viewRef.value
  if (!el) return

  if (maximized) {
    savedRect.value = el.getBoundingClientRect()
    const { top, left, width, height } = savedRect.value

    Object.assign(el.style, {
      position: 'fixed',
      margin: '0',
      zIndex: '101',
      transition: 'none',
      top: `${top}px`,
      left: `${left}px`,
      width: `${width}px`,
      height: `${height}px`,
      borderRadius: '',
    })

    void el.offsetHeight

    Object.assign(el.style, {
      transition: TRANSITION,
      top: `${GAP}px`,
      left: `${GAP}px`,
      width: `calc(100vw - ${GAP * 2}px)`,
      height: `calc(100dvh - ${GAP * 2}px)`,
      borderRadius: RADIUS,
    })
  } else if (savedRect.value) {
    const { top, left, width, height } = savedRect.value

    Object.assign(el.style, {
      transition: TRANSITION,
      top: `${top}px`,
      left: `${left}px`,
      width: `${width}px`,
      height: `${height}px`,
      borderRadius: '',
    })

    setTimeout(() => {
      el.removeAttribute('style')
      savedRect.value = null
    }, DURATION)
  }
})

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && isMaximized.value) {
    isMaximized.value = false
  }
}

function onDetailsVisibilityChange(visible: boolean): void {
  if (!visible) lineageStore.setDetailedArtifact(null)
}

async function loadLineage(): Promise<boolean> {
  try {
    await lineageStore.load()
    return true
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to load lineage')))
    return false
  }
}

async function confirmDiscardChanges(): Promise<boolean> {
  if (!lineageStore.hasEdits) return true

  return new Promise((resolve) => {
    let settled = false
    const finish = (result: boolean): void => {
      if (settled) return
      settled = true
      if (result) {
        lineageStore.discardChanges()
        lineageStore.setDetailedArtifact(null)
      }
      resolve(result)
    }

    confirm.require(
      discardLineageChangesConfirmOptions(
        () => finish(true),
        () => finish(false),
        () => finish(false),
      ),
    )
  })
}

async function onDepthChange(depth: number): Promise<void> {
  if (depth === lineageStore.depth) return
  const previousDepth = lineageStore.depth
  if (!(await confirmDiscardChanges())) return

  lineageStore.setDepth(depth)
  if (!(await loadLineage())) lineageStore.setDepth(previousDepth)
}

watch(
  () => [route.params.artifactId, artifactsStore.currentArtifact?.id] as const,
  ([artifactId, currentArtifactId]) => {
    if (typeof artifactId !== 'string' || artifactId !== currentArtifactId) return
    lineageStore.setDetailedArtifact(null)
    void loadLineage()
  },
  { immediate: true },
)

onBeforeRouteLeave(confirmDiscardChanges)
onBeforeRouteUpdate(confirmDiscardChanges)

onMounted(() => window.addEventListener('keydown', onKeydown))
onUnmounted(() => window.removeEventListener('keydown', onKeydown))
</script>

<style scoped>
.view {
  height: calc(100vh - 310px);
  background-color: var(--p-card-background);
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  overflow: hidden;
  box-shadow: var(--card-shadow);
}
</style>

<style>
.backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: 100;
  cursor: pointer;
}

.backdrop-enter-active,
.backdrop-leave-active {
  transition: opacity 0.35s ease;
}
.backdrop-enter-from,
.backdrop-leave-to {
  opacity: 0;
}
</style>
