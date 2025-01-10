<template>
  <div class="wrapper">
    <div class="body">
      <div class="content">
        <div class="headings">
          <h1 class="main-title">{{ title }}</h1>
          <h3 v-if="subTitle" class="sub-title">{{ subTitle }}</h3>
        </div>
        <div class="form-wrapper">
          <slot name="form"></slot>
        </div>
        <template v-if="services && !hideSso">
          <span class="line">or</span>
          <div class="services">
            <d-button
              v-for="service in services"
              :key="service.id"
              variant="outlined"
              class="button-plain"
              link
              @click="() => service.action()"
            >
              <span class="service-label">{{ service.label }}</span>
              <img :src="service.icon" alt="" width="24" height="24" class="icon" />
            </d-button>
            <d-message v-if="servicesError" severity="error" size="small" variant="simple">
              {{ servicesError }}
            </d-message>
          </div>
        </template>

        <div class="footer">
          <slot name="footer"></slot>
        </div>
      </div>
    </div>
    <div class="image">
      <img :src="image" alt="dataforce.studio" class="img" />
    </div>
  </div>
</template>

<script setup lang="ts">
import type { IAuthorizationService, TAuthorizationWrapperProps } from './interfaces'

import GoogleIcon from '@/assets/img/authorization-services/google.svg'
// import MicrosoftIcon from '@/assets/img/authorization-services/microsoft.svg'
// import GitHubIcon from '@/assets/img/authorization-services/github.svg'

import { useAuthStore } from '@/stores/auth'
import { onBeforeMount, ref } from 'vue'
import { useRouter } from 'vue-router'

const authStore = useAuthStore()
const router = useRouter()

defineProps<TAuthorizationWrapperProps>()

const servicesError = ref('')

const services: IAuthorizationService[] = [
  {
    id: 'google',
    label: 'Sign in with Google',
    icon: GoogleIcon,
    action: () =>
      (window.location.href = `${import.meta.env.VITE_DATAFORCE_API_URL}/auth/google/login`),
  },
  // {
  //   id: 'microsoft',
  //   label: 'Sign in with Microsoft',
  //   icon: MicrosoftIcon,
  //   action: () => console.log('Microsoft'),
  // },
  // {
  //   id: 'github',
  //   label: 'Sign in with Github',
  //   icon: GitHubIcon,
  //   action: () => console.log('Github'),
  // },
]

onBeforeMount(async () => {
  const urlParams = new URLSearchParams(window.location.search)
  const code = urlParams.get('code')

  if (!code) return

  try {
    await authStore.loginWithGoogle(code)

    router.push({ name: 'home' })
  } catch (e) {
    console.error(e)
  }
})
</script>

<style scoped>
.wrapper {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  background-color: var(--color-card-background);
  border-radius: 16px;
  max-width: 1360px;
  min-height: 746px;
  margin: 0 auto;
  overflow: hidden;
  box-shadow: var(--card-shadow);
}

.body {
  padding: 48px 64px;
  align-self: center;
}

.content {
  max-width: 399px;
  width: 100%;
  margin: 0 auto;
}

.form-wrapper {
  margin-bottom: 20px;
}

.headings {
  margin-bottom: 32px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.main-title {
  font-weight: 600;
}

.sub-title {
  color: var(--color-text-muted);
  font-size: 16px;
}

.form-wrapper {
  margin-bottom: 24px;
}

.line {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 10px;
  align-items: center;
  line-height: 1;
  margin-bottom: 24px;
  color: var(--color-text-muted);

  &::before,
  &::after {
    content: '';
    height: 1px;
    background-color: var(--color-divider-border);
  }
}

.services {
  display: flex;
  flex-direction: column;
  gap: 20px;
  margin-bottom: 32px;
}

.button-plain {
  border-color: var(--p-inputtext-border-color);
  color: var(--p-button-text-plain-color);
}

.button-plain:not(:disabled):hover {
  background-color: var(--p-button-outlined-plain-hover-background);
  border-color: var(--p-inputtext-border-color);
  color: var(--p-button-text-plain-color);
}

.button-plain:not(:disabled):active {
  background-color: var(--p-button-outlined-plain-active-background);
  border-color: var(--p-inputtext-border-color);
  color: var(--p-button-text-plain-color);
}

.service-label {
  font-weight: 500;
}

.icon {
  width: 24px;
  height: 24px;
  object-fit: contain;
}

.footer {
  text-align: center;
  color: var(--color-text-muted);
}

.image {
  position: relative;
}

.img {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

@media (max-width: 992px) {
  .wrapper {
    max-width: 527px;
    display: block;
  }

  img {
    display: none;
  }
}

@media (max-width: 768px) {
  .body {
    padding: 30px;
  }
}
</style>
