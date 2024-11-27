import { Rabbit, Timer, FolderDot } from 'lucide-vue-next'

export const sidebarMenu = [
  {
    id: 1,
    label: 'Express task',
    icon: Rabbit,
    route: 'home',
  },
  {
    id: 2,
    label: 'Run time',
    icon: Timer,
    route: 'sign-up',
    disabled: true,
    tooltipMessage: 'Coming soon!',
  },
  {
    id: 3,
    label: 'Projects',
    icon: FolderDot,
    route: 'sign-up',
    disabled: true,
    tooltipMessage: 'Coming soon!',
  },
]
