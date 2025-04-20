export interface TaskData {
  id: number
  icon: string
  title: string
  description: string
  btnText?: string
  linkName?: string
  tooltipData: string
  analyticsTaskName: string
}

export interface TaskList {
  label: string
  tasks: TaskData[]
}
