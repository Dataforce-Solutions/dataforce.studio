export interface ITaskData {
  id: number
  icon: string
  title: string
  description: string
  btnText?: string
  linkName?: string
  tooltipData: string
}

export interface ITasksList {
  label: string
  tasks: ITaskData[]
}
