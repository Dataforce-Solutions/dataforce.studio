import type { PromptNode } from '@/components/prompt-fusion/interfaces'
import { useVueFlow } from '@vue-flow/core'
import { computed, ref } from 'vue'

export const usePromptFusion = () => {
  const { onNodeClick, onPaneClick } = useVueFlow()

  const activeNode = ref<PromptNode | null>(null)

  const getActiveNode = computed(() => activeNode.value)

  onNodeClick((event) => {
    activeNode.value = event.node as PromptNode
  })
  onPaneClick(() => {
    activeNode.value = null
  })

  return { getActiveNode }
}
