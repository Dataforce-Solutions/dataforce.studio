import type { ITaskData } from './types'
import TabularClassificationIcon from '@/assets/img/cards-icons/tabular-classification.svg'
import TabularRegressionIcon from '@/assets/img/cards-icons/tabular-regression.svg'
import ForecastingIcon from '@/assets/img/cards-icons/forecasting.svg'
import ConversationalQAIcon from '@/assets/img/cards-icons/conversational-qa.svg'

type IAppTaskData = ITaskData & {
  isAvailable: boolean
}

const appTasks: IAppTaskData[] = [
  {
    id: 1,
    icon: TabularClassificationIcon,
    title: 'Tabular Classification',
    description: 'Technique for categorizing table-structured data by labeled classes.',
    btnText: 'next',
    linkName: 'home',
    tooltipData:
      'Lorem ipsum dolor sit amet consectetur adipisicing elit. Sequi sint minima labore ab tempora minus dolores repudiandae, tempore voluptate tenetur illo obcaecati, recusandae quae ipsa excepturi ad quia perspiciatis autem?',
    isAvailable: true,
  },
  {
    id: 2,
    icon: TabularRegressionIcon,
    title: 'Tabular Regression',
    description: 'Technique for categorizing table-structured data by labeled classes.',
    btnText: 'next',
    linkName: 'home',
    tooltipData:
      'Lorem ipsum dolor sit amet consectetur adipisicing elit. Sequi sint minima labore ab tempora minus dolores repudiandae, tempore voluptate tenetur illo obcaecati, recusandae quae ipsa excepturi ad quia perspiciatis autem?',
    isAvailable: true,
  },
  {
    id: 3,
    icon: ForecastingIcon,
    title: 'Forecasting',
    description: 'Process of predicting future values based on historical data and trends.',
    tooltipData:
      'Lorem ipsum dolor sit amet consectetur adipisicing elit. Sequi sint minima labore ab tempora minus dolores repudiandae, tempore voluptate tenetur illo obcaecati, recusandae quae ipsa excepturi ad quia perspiciatis autem?',
    isAvailable: false,
  },
  {
    id: 4,
    icon: ConversationalQAIcon,
    title: 'Conversational QA',
    description: 'An interactive system answering questions through dialogue.',
    tooltipData:
      'Lorem ipsum dolor sit amet consectetur adipisicing elit. Sequi sint minima labore ab tempora minus dolores repudiandae, tempore voluptate tenetur illo obcaecati, recusandae quae ipsa excepturi ad quia perspiciatis autem?',
    isAvailable: false,
  },
]

export const availableTasks: ITaskData[] = appTasks.filter((task) => task.isAvailable)
export const notAvailableTasks: ITaskData[] = appTasks.filter((task) => !task.isAvailable)
