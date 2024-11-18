import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { addComponents } from './components'

export const initPrimeVue = (app: App) => {
  app.use(PrimeVue, {
    theme: {
      preset: Aura,
    },
  })

  addComponents(app)
}
