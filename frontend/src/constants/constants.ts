import type { TaskData } from '@/components/homepage-tasks/interfaces'

import { FolderDot, CirclePlay, Zap } from 'lucide-vue-next'
import TabularClassificationIcon from '@/assets/img/cards-icons/tabular-classification.svg'
import TabularRegressionIcon from '@/assets/img/cards-icons/tabular-regression.svg'
import ForecastingIcon from '@/assets/img/cards-icons/forecasting.svg'
import ConversationalQAIcon from '@/assets/img/cards-icons/conversational-qa.svg'

export const sidebarMenu = [
  {
    id: 1,
    label: 'Express task',
    icon: Zap,
    route: 'home',
  },
  {
    id: 2,
    label: 'Run time',
    icon: CirclePlay,
    route: 'runtime',
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

type IAppTaskData = TaskData & {
  isAvailable: boolean
}

const appTasks: IAppTaskData[] = [
  {
    id: 1,
    icon: TabularClassificationIcon,
    title: 'Tabular Classification',
    description: 'Technique for categorizing table-structured data by labeled classes.',
    btnText: 'next',
    linkName: 'classification',
    tooltipData:
      'Applied in fields like healthcare for disease diagnosis, finance for credit risk evaluation, marketing for customer segmentation, and retail for predicting product categories',
    isAvailable: true,
  },
  {
    id: 2,
    icon: TabularRegressionIcon,
    title: 'Tabular Regression',
    description: 'Technique for categorizing table-structured data by labeled classes.',
    btnText: 'next',
    linkName: 'regression',
    tooltipData:
      'Works best for structured datasets, ideal for fields like finance, healthcare, real estate, and energy, where precise value predictions are crucial',
    isAvailable: true,
  },
  {
    id: 3,
    icon: ForecastingIcon,
    title: 'Forecasting',
    description: 'Process of predicting future values based on historical data and trends.',
    tooltipData:
      'Ideal for time-series data, commonly used in finance, retail, energy, and weather prediction to anticipate future trends or demands',
    isAvailable: false,
  },
  {
    id: 4,
    icon: ConversationalQAIcon,
    title: 'Conversational QA',
    description: 'An interactive system answering questions through dialogue.',
    tooltipData:
      'Used in customer service to resolve inquiries, education for tutoring, healthcare for symptom checks, and e-commerce for guiding purchases',
    isAvailable: false,
  },
]

export const availableTasks = appTasks.filter((task) => task.isAvailable)
export const notAvailableTasks = appTasks.filter((task) => !task.isAvailable)
