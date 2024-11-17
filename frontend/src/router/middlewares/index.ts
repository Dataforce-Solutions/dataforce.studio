import type { Router } from 'vue-router'
import { loadLayoutMiddleware } from './LoadLayoutMiddleware'

export const installMiddlewares = (router: Router) => {
  router.beforeEach(loadLayoutMiddleware)
}
