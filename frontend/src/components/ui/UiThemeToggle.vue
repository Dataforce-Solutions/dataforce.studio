<template>
  <div class="custom-toggle" :class="{ dark: modelValue === 'dark' }">
    <div class="custom-toggle-wrapper" @click="click">
      <div class="custom-toggle-item">
        <sun :size="14" />
      </div>
      <div class="custom-toggle-item">
        <moon :size="14" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { Theme } from '@/stores/theme'
import { Sun, Moon } from 'lucide-vue-next'

type Props = {
  modelValue: Theme
}
type Emits = {
  'update:modelValue': [Theme]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

function click() {
  const newTheme: Theme = props.modelValue === 'dark' ? 'light' : 'dark'
  emit('update:modelValue', newTheme)
}
</script>

<style scoped>
.custom-toggle-wrapper {
  display: flex;
  gap: 6px;
  padding: 4px;
  border-radius: 16px;
  background-color: var(--p-toggleswitch-background);
  cursor: pointer;
  position: relative;
}
.custom-toggle-wrapper::before{
  content:'';
  width: 18px;
  height: 18px;
  border-radius: 50%;
  position: absolute;
  top: 4px;
  right: 4px;
  background-color: var(--p-toggleswitch-background);
  z-index: 2;
  transition: right .5s;
}
.dark .custom-toggle-wrapper::before {
  right: 28px;
}
.custom-toggle-item {
  width: 18px;
  height: 18px;
  display: flex;
  justify-content: center;
  align-items: center;
  border-radius: 50%;
  background-color: transparent;
  color: var(--p-toggleswitch-handle-color);
}
</style>
