import { DataTableArquero, type SelectTableEvent } from '@/lib/data-table/DataTableArquero'
import type { FilterItem } from '@/lib/data-table/interfaces'
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

type StartedColumnData = {
  fileSize: number
  fileName: string
  columnsCount: number
  rowsCount: number
  columnNames: string[]
  values: object[]
}

export type ColumnType = 'number' | 'string' | 'date'

export const useDataTable = (validator: Function) => {
  const dataTable = new DataTableArquero()

  const startedTableData = ref<StartedColumnData | null>()
  const columnsCount = ref<number | undefined>()
  const rowsCount = ref<number | undefined>()
  const target = ref('')
  const group = ref<string[]>([])
  const selectedColumns = ref<string[]>([])
  const filters = ref<FilterItem[]>([])
  const viewValues = ref<object[] | null>(null)
  const columnTypes = ref<Record<string, ColumnType>>({})

  const isTableExist = computed(() => !!startedTableData.value)
  const fileData = computed(() => ({
    name: startedTableData.value?.fileName,
    size: startedTableData.value?.fileSize,
  }))
  const uploadDataErrors = computed(() =>
    validator(
      startedTableData.value?.fileSize,
      startedTableData.value?.columnsCount,
      startedTableData.value?.rowsCount,
    ),
  )
  const isUploadWithErrors = computed(() => {
    const errors = uploadDataErrors.value
    for (const key in errors) {
      if (errors[key as keyof typeof errors]) return true
    }
    return false
  })
  const getAllColumnNames = computed(() => startedTableData.value?.columnNames || [])
  const getTarget = computed(() => target.value)
  const getGroup = computed(() => group.value)
  const getFilters = computed(() => filters.value)

  async function onSelectFile(file: File) {
    await dataTable.createFormCSV(file)
    rewriteValues()
  }
  function onRemoveFile() {
    dataTable.clearTable()
    viewValues.value = null
    setColumnTypes({})
  }
  function setColumnTypes(row: object) {
    for (const key in row) {
      if (Number(row[key as keyof typeof row])) columnTypes.value[key] = 'number'
      else columnTypes.value[key] = 'string'
    }
  }
  function onColumnsCountChanged(count: number | undefined) {
    columnsCount.value = count
  }
  function onRowsCountChanged(count: number | undefined) {
    rowsCount.value = count
  }
  function onSelectTable(event: SelectTableEvent) {
    if (!event) {
      startedTableData.value = null
    } else {
      const columnsCount = dataTable.getColumnsCount()
      const rowsCount = dataTable.getRowsCount()
      const columnNames = dataTable.getColumnNames()
      const values = dataTable.getObjects()

      target.value = columnNames[columnNames.length - 1]
      setColumnTypes(values[0])

      startedTableData.value = {
        fileSize: event.size,
        fileName: event.name,
        columnsCount,
        rowsCount,
        columnNames,
        values,
      }
    }
  }
  function setTarget(column: string) {
    if (!getGroup.value.includes(column)) target.value = column
  }
  function changeGroup(column: string) {
    if (target.value === column) return

    group.value.includes(column)
      ? (group.value = group.value.filter((item) => item !== column))
      : group.value.push(column)
  }
  function rewriteValues() {
    viewValues.value = dataTable.getObjects()
  }
  function downloadCSV() {
    dataTable.downloadCSV('dataforce')
  }
  function setSelectedColumns(columns: string[]) {
    dataTable.setSelectedColumns(columns)
    selectedColumns.value = dataTable.getSelectedColumns()
    rewriteValues()
    onColumnsCountChanged(dataTable.getColumnsCount())
  }
  function setFilters(newFilters: FilterItem[]) {
    dataTable.setFilters(newFilters)
    filters.value = newFilters
    rewriteValues()
  }
  function getDataForTraining() {
    return dataTable.getDataForTraining()
  }

  watch(startedTableData, (value) => {
    onColumnsCountChanged(value?.columnsCount)
    onRowsCountChanged(value?.rowsCount)
  })

  onMounted(() => {
    dataTable.on('SELECT_TABLE', onSelectTable)
  })

  onBeforeUnmount(() => {
    dataTable.off('SELECT_TABLE', onSelectTable)
    onRemoveFile()
  })
  return {
    isTableExist,
    fileData,
    uploadDataErrors,
    isUploadWithErrors,
    columnsCount,
    rowsCount,
    getAllColumnNames,
    viewValues,
    getTarget,
    getGroup,
    selectedColumns,
    getFilters,
    columnTypes,
    onSelectFile,
    onRemoveFile,
    setTarget,
    changeGroup,
    setSelectedColumns,
    downloadCSV,
    setFilters,
    getDataForTraining
  }
}
