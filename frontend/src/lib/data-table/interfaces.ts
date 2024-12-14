export interface IDataTable {
  createTable(file: File): Promise<void>
  downloadCSV(fileName: string): void
  getColumnsCount(): number
  getRowsCount(): number
  clearTable(): void
}
