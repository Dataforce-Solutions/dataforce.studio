<template>
  <div class="area" :style="{ width, height: width }" @click="inputRef?.click()">
    <img :src="newImage || image" alt="" class="image" />
    <input
      ref="inputRef"
      type="file"
      id="avatar"
      name="avatar"
      accept="image/png, image/jpeg"
      class="input"
      @change="onInputChange"
    />
  </div>
</template>

<script setup lang="ts">
import avatarPlaceholder from '@/assets/img/avatar-placeholder.png'
import { ref } from 'vue'

type TEmits = {
  (e: 'onImageChange', file: File | null): void
}

defineProps({
  width: {
    type: String,
    default: '100px',
  },
  image: {
    type: String,
    default: avatarPlaceholder,
  },
})

const emit = defineEmits<TEmits>()

const inputRef = ref<HTMLInputElement>()

const newImage = ref('')

const onInputChange = (event: Event) => {
  const input = event.target as HTMLInputElement

  if (!input.files || !(input.files.length > 0)) {
    emit('onImageChange', null)

    newImage.value = ''

    return
  }

  const file = input.files[0]

  emit('onImageChange', file)

  const reader = new FileReader()

  reader.onload = (e) => {
    newImage.value = (e.target?.result as string) || ''
  }

  reader.readAsDataURL(file)
}
</script>

<style scoped>
.area {
  position: relative;
  border-radius: 50%;
  overflow: hidden;
  cursor: pointer;
}
.image {
  width: 100%;
  height: 100%;
  object-fit: cover;
}
.input {
  position: absolute;
  top: 0;
  left: 0;
  width: 0;
  height: 0;
  opacity: 0;
}
</style>
