import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'

export const useThemeStore = defineStore('theme', () => {
  const theme = ref('light')

  const getCurrentTheme = computed(() => theme.value)

  const toggleTheme = () => {
    theme.value = theme.value === 'light' ? 'dark' : 'light'
  }

  const changeTheme = () => {
    toggleTheme()

    localStorage.setItem('theme', theme.value)
  }

  const checkTheme = () => {
    const themeInLocalstorage = localStorage.getItem('theme')

    if (themeInLocalstorage) {
      theme.value = themeInLocalstorage
    } else {
      theme.value = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'

      window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
        if (!localStorage.getItem('theme')) toggleTheme()
      })
    }
  }

  watch(theme, (t) => {
    document.documentElement.dataset.theme = theme.value
  })

  return { getCurrentTheme, changeTheme, checkTheme }
})
