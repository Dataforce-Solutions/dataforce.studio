<template>
  <div class="content">
    <!--<ImageInput
      shape="square"
      :image="Placeholder"
      class="photo"
      @on-image-change="onImageChange"
    />-->
    <Avatar size="xlarge" :label="avatarLabel" />
    <Form :initialValues :resolver @submit="onFormSubmit" class="body">
      <label for="name" class="label">Name</label>
      <InputText v-model="initialValues.name" name="name" id="name" class="input" />
      <Button type="submit" rounded fluid :loading="loading">Create</Button>
    </Form>
  </div>
</template>

<script setup lang="ts">
import { InputText, Button, Avatar } from 'primevue'
import ImageInput from '../ui/ImageInput.vue'
import Placeholder from '@/assets/img/form-bg.webp'
import { computed, reactive, ref } from 'vue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { z } from 'zod'
import { useOrganizationStore } from '@/stores/organization'
import { useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'

type Emits = {
  close: []
}

const emits = defineEmits<Emits>()

const organizationStore = useOrganizationStore()
const toast = useToast()

const resolver = zodResolver(
  z.object({
    name: z.string().min(3),
  }),
)

const logo = ref<File | null>(null)
const loading = ref(false)
const initialValues = reactive({
  name: '',
})

const avatarLabel = computed(() => {
  return initialValues.name.charAt(0).toUpperCase()
})

function onImageChange(event: File | null) {
  logo.value = event
}

async function onFormSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  const payload = {
    logo: 'https://framerusercontent.com/images/Ks0qcMuaRUt9YEMHOZIkAAXLwl0.png',
    name: values.name,
  }
  try {
    loading.value = true
    await organizationStore.createOrganization(payload)
    toast.add(simpleSuccessToast('Your organization is ready. You can now switch to it from the organization menu.'))
    emits('close')
  } catch (e: any) {
    toast.add(simpleErrorToast(e.message || 'Could not create organization'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.photo {
  margin-bottom: 20px;
}
.body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
}
.input {
  margin-bottom: 28px;
}
</style>
