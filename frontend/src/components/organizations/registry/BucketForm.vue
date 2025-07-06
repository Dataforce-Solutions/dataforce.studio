<template>
  <Form v-slot="$form" :initial-values="initialValues" :resolver="resolver" @submit="onSubmit">
    <div class="inputs">
      <div class="field">
        <label for="endpoint" class="label required">Endpoint</label>
        <InputText
          v-model="initialValues.endpoint"
          id="endpoint"
          name="endpoint"
          type="text"
          placeholder="e.g. s3.amazonaws.com"
          fluid
        />
        <div v-if="($form as any).endpoint?.invalid" class="message">Please enter a valid endpoint URL</div>
      </div>
      <div class="field">
        <label for="bucket_name" class="label required">Bucket name</label>
        <InputText
          v-model="initialValues.bucket_name"
          id="bucket_name"
          name="bucket_name"
          type="text"
          placeholder="e.g. dataforce-storage"
          fluid
        />
        <div v-if="($form as any).bucket_name?.invalid" class="message">Please enter a name for the bucket</div>
      </div>
      <div class="field">
        <label for="access_key" class="label">Access key</label>
        <InputText
          v-model="initialValues.access_key"
          id="access_key"
          name="access_key"
          type="text"
          placeholder="Enter access key"
          fluid
        />
      </div>
      <div class="field">
        <label for="secret_key" class="label">Secret key</label>
        <InputText
          v-model="initialValues.secret_key"
          id="secret_key"
          name="secret_key"
          type="text"
          placeholder="Enter secret key"
          fluid
        />
      </div>
      <div class="field">
        <label for="region" class="label">Region</label>
        <InputText
          v-model="initialValues.region"
          id="region"
          name="region"
          type="text"
          placeholder="e.g. us-west-2"
          fluid
        />
      </div>
    </div>

    <div class="field field--protocol">
      <label class="label">Secure (http/https)</label>
      <ToggleSwitch v-model="initialValues.secure" name="secure" />
    </div>

    <Button type="submit" fluid rounded :loading="loading">Create</Button>
  </Form>
</template>

<script setup lang="ts">
import type { BucketSecretCreator } from '@/lib/api/bucket-secrets/interfaces'
import { onMounted, ref } from 'vue'
import { z } from 'zod'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { Button, InputText, ToggleSwitch } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'


type Props = {
  initialData?: BucketSecretCreator
  loading: boolean
}

type Emits = {
  submit: [BucketSecretCreator]
}

const props = defineProps<Props>()
const emits = defineEmits<Emits>()

const initialValues = ref<BucketSecretCreator>({
  endpoint: '',
  bucket_name: '',
  access_key: '',
  secret_key: '',
  session_token: '',
  secure: true,
  region: '',
})

const resolver = zodResolver(
  z.object({
    endpoint: z.string().min(1),
    bucket_name: z.string().min(1),
    access_key: z.string(),
    secret_key: z.string(),
    session_token: z.string(),
    region: z.string(),
  }),
)

function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return

  emits('submit', { ...initialValues.value })
}

function patchForm(data: BucketSecretCreator) {
  initialValues.value = { ...data }
}

onMounted(() => {
  if (props.initialData) patchForm(props.initialData)
})
</script>

<style scoped>
.inputs {
  display: flex;
  flex-direction: column;
  margin-bottom: 20px;
  gap: 12px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.label {
  align-self: flex-start;
  font-size: 14px;
  line-height: 1.5;
  display: flex;
  align-items: center;
  gap: 8px;
}
.field--protocol {
  flex-direction: row;
  gap: 12px;
  margin-bottom: 28px;
}
.message {
  font-size: 12px;
  line-height: 1.75;
}
</style>
