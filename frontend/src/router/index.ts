import { createRouter, createWebHistory } from 'vue-router'
import { AppLayoutsEnum } from '@/templates/templates.types'
import { installMiddlewares } from './middlewares'

import HomePage from '@/pages/HomePage.vue'

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomePage,
    },
    {
      path: '/sign-up',
      name: 'sign-up',
      component: () => import('../pages/SignUpPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/sign-in',
      name: 'sign-in',
      component: () => import('../pages/SignInPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
  ],
})

installMiddlewares(router)

export default router
