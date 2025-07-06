import type { Router } from 'vue-router'
import { loadLayoutMiddleware } from './LoadLayoutMiddleware'
import { authMiddleware } from './AuthMiddleware'

export const installMiddlewares = (router: Router) => {
  router.beforeEach(loadLayoutMiddleware)
  router.beforeEach(authMiddleware)
}
