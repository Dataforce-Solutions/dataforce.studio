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
    {
      path: '/forgot-password',
      name: 'forgot-password',
      component: () => import('../pages/ForgotPasswordPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/change-password',
      name: 'change-password',
      component: () => import('../pages/ChangePasswordPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/email-check',
      name: 'email-check',
      component: () => import('../pages/EmailCheckPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
    {
      path: '/email-confirmed',
      name: 'email-confirmed',
      component: () => import('../pages/EmailConfirmedPage.vue'),
      meta: {
        layout: AppLayoutsEnum.clear,
      },
    },
  ],
})

installMiddlewares(router)

export default router
