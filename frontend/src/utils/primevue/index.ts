import type { App } from 'vue'
import PrimeVue from 'primevue/config'
import { addComponents } from './components'
import { addDirectives } from './directives'
import { dPreset } from './preset'

export const initPrimeVue = (app: App) => {
  app.use(PrimeVue, {
    theme: {
      preset: dPreset,
    },
  })

  addComponents(app)
  addDirectives(app)
}
