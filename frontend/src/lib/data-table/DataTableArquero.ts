import { ColumnTable, fromCSV } from 'arquero'
import type { IDataTable } from './interfaces'
import { Observable } from '@/utils/observable/Observable'

export type Events = {
  COLUMNS_COUNT_CHANGED: number | undefined
  ROWS_COUNT_CHANGED: number | undefined
}

export class DataTableArquero extends Observable<Events> implements IDataTable {
  private dataTable: ColumnTable | null

  constructor() {
    super()

    this.dataTable = null
  }

  async createFormCSV(file: File) {
    this.dataTable = fromCSV(await file.text())

    this.emit('COLUMNS_COUNT_CHANGED', this.getColumnsCount())
    this.emit('ROWS_COUNT_CHANGED', this.getRowsCount())
  }

  async downloadCSV(fileName: string = 'output.csv') {
    if (!this.dataTable) throw new Error('You need createTable before')

    const csvContent = this.dataTable.toCSV()

    const blob = new Blob([csvContent], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    a.style.display = 'none'
    document.body.appendChild(a)
    a.click()

    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  getColumnsCount(): number {
    if (!this.dataTable) throw new Error('You need createTable before')

    return this.dataTable.numCols()
  }

  getRowsCount(): number {
    if (!this.dataTable) throw new Error('You need createTable before')

    return this.dataTable.numRows()
  }

  clearTable(): void {
    this.dataTable = null

    this.emit('COLUMNS_COUNT_CHANGED')
    this.emit('ROWS_COUNT_CHANGED')
  }
}
