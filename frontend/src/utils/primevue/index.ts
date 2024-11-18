import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import Aura from '@primevue/themes/aura'
import { addComponents } from './components'
import { addDirectives } from './directives'

export const initPrimeVue = (app: App) => {
  app.use(PrimeVue, {
    theme: {
      preset: Aura,
    },
  })

  addComponents(app)
  addDirectives(app)
}
