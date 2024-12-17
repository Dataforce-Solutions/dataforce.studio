import type { IMetricCard } from '@/components/services/services.interfaces'

export const metricCardsData: IMetricCard[] = [
  {
    title: 'Balanced accuracy',
    items: [
      {
        id: 1,
        label: 'Test',
        value: 12.567,
        primary: true,
      },
      {
        id: 2,
        label: 'Training',
        value: 11.594,
      },
    ],
  },
  {
    title: 'Precision',
    items: [
      {
        id: 1,
        label: 'Test',
        value: 12.567,
        primary: true,
      },
      {
        id: 2,
        label: 'Training',
        value: 11.594,
      },
    ],
  },
  {
    title: 'Recall',
    items: [
      {
        id: 1,
        label: 'Test',
        value: 12.567,
        primary: true,
      },
      {
        id: 2,
        label: 'Training',
        value: 11.594,
      },
    ],
  },
  {
    title: 'F1 score',
    items: [
      {
        id: 1,
        label: 'Test',
        value: 12.567,
        primary: true,
      },
      {
        id: 2,
        label: 'Training',
        value: 11.594,
      },
    ],
  },
]
