import type { App } from 'vue'
import { Button, Card } from 'primevue'

export const addComponents = (app: App) => {
  app.component('DButton', Button)
  app.component('DCard', Card)
}
