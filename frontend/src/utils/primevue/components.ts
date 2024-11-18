import type { App } from 'vue'
import { Button, Card, InputText, Message } from 'primevue'
import { Form } from '@primevue/forms'

export const addComponents = (app: App) => {
  app.component('DButton', Button)
  app.component('DCard', Card)
  app.component('DInputText', InputText)
  app.component('DMessage', Message)
  app.component('DForm', Form)
}
