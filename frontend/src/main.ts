import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'

import { initPrimeVue } from './utils/primevue'

const app = createApp(App)

app.use(createPinia())
app.use(router)

initPrimeVue(app)

app.mount('#app')
