export interface IMetricCard {
  title: string
  items: {
    id: number
    label: string
    value: number
    primary?: boolean
  }[]
}
