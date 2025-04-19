<template>
  <d-form class="form" v-slot="$form" :initialValues :resolver :validateOnValueUpdate="false" :validateOnSubmit="true" :validateOnBlur="true" @submit="onFormSubmit">
    <div class="input-wrapper">
      <d-float-label variant="on">
        <d-input-text id="email" name="email" type="email" autocomplete="off" fluid v-model="initialValues.email" class="input" variant="filled"/>
        <label for="email" class="label">Email</label>
      </d-float-label>
      <d-message v-if="$form.email?.invalid" severity="error" size="small" variant="simple" class="message">
        {{ $form.email.error?.message }}
      </d-message>
    </div>
    <d-button type="submit" class="button">
      <span>Get early access</span>
      <arrow-right :size="14"/>
    </d-button>
  </d-form>
</template>

<script setup lang="ts">
import type { FormSubmitEvent } from '@primevue/forms'
import { ref } from 'vue'
import { ArrowRight } from 'lucide-vue-next'
import { useToast } from 'primevue'
import { simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { forgotPasswordInitialValues } from '@/utils/forms/initialValues'
import { forgotPasswordResolver } from '@/utils/forms/resolvers'

const toast = useToast()

const initialValues = ref(forgotPasswordInitialValues)
const resolver = ref(forgotPasswordResolver)

const onFormSubmit = async ({ valid }: FormSubmitEvent) => {
  if (!valid) return
  toast.add(
    simpleSuccessToast('We’ll notify you as soon as Orbits is ready for early access.', 'You’re on the list!')
  )
}
</script>

<style scoped>
.form {
  max-width: 450px;
  width: 100%;
  display: flex;
  align-items: flex-start;
  gap: 12px;
}

.input-wrapper {
  flex: 1 1 auto;
  position: relative;
}

.input {
  height: 40px;
}

.message {
  position: absolute;
  top: calc(100% + 5px);
}

.button {
  flex: 0 0 auto;
  height: 40px;
}

@media (max-width:768px){
  .form {
    flex-direction: column;
    align-items: stretch;
  }
}
</style>
