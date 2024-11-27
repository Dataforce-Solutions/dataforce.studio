import { X, PencilLine } from 'lucide-vue-next'
import { computed, onMounted, ref, type Ref } from 'vue'

export const useInputIcon = (inputs: Ref[]) => {
  const inputsStates = ref<Record<string, boolean>>({})

  const getCurrentInputIcon = computed(
    () => (inputName: string) => (inputsStates.value[inputName] ? X : PencilLine),
  )

  function setInputState(inputName: string, state: boolean) {
    inputsStates.value[inputName] = state
  }

  onMounted(() => {
    inputs.reduce((obj: any, input) => {
      if (!input.value) return obj

      const el = input.value.$el as HTMLInputElement

      el.onblur = () => setInputState(el.name, false)
      el.onfocus = () => setInputState(el.name, true)

      obj[el.name] = false
      return obj
    }, {})
  })

  return { getCurrentInputIcon }
}
