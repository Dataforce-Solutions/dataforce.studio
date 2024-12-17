export interface IDataTable {
  createFormCSV(file: File): Promise<void>
  downloadCSV(fileName: string): void
  getColumnsCount(): number
  getRowsCount(): number
  clearTable(): void
}
