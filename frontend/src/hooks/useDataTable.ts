import { DataTableArquero } from '@/lib/data-table/DataTableArquero'
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

export const useDataTable = () => {
  const dataTable = new DataTableArquero()

  const isTableExist = ref(false)
  const fileSize = ref<number | undefined>()
  const fileName = ref<string | undefined>()
  const tableColumnsCount = ref<number | undefined>()
  const tableRowsCount = ref<number | undefined>()

  const fileData = computed(() => ({
    name: fileName.value,
    size: fileSize.value,
  }))

  const uploadDataErrors = computed(() => ({
    size: !!(fileSize.value && fileSize.value > 1024 * 1024),
    columns: !!(tableColumnsCount.value && tableColumnsCount.value <= 3),
    rows: !!(tableRowsCount.value && tableRowsCount.value <= 100),
  }))

  const isUploadWithErrors = computed(() => {
    const errors = uploadDataErrors.value

    for (const key in errors) {
      if (errors[key as keyof typeof errors]) return true
    }

    return false
  })

  async function onSelectFile(file: File) {
    await dataTable.createFormCSV(file)

    isTableExist.value = true
    fileSize.value = file.size
    fileName.value = file.name
  }

  function onRemoveFile() {
    dataTable.clearTable()

    isTableExist.value = false
    fileSize.value = undefined
    fileName.value = undefined
  }

  function onColumnsCountChanged(columnsCount: number | undefined) {
    tableColumnsCount.value = columnsCount
  }

  function onRowsCountChanged(rowsCount: number | undefined) {
    tableRowsCount.value = rowsCount
  }

  onMounted(() => {
    dataTable.on('COLUMNS_COUNT_CHANGED', onColumnsCountChanged)
    dataTable.on('ROWS_COUNT_CHANGED', onRowsCountChanged)
  })

  onBeforeUnmount(() => {
    dataTable.off('COLUMNS_COUNT_CHANGED', onColumnsCountChanged)
    dataTable.off('COLUMNS_COUNT_CHANGED', onRowsCountChanged)

    onRemoveFile()
  })
  return {
    isTableExist,
    fileData,
    uploadDataErrors,
    isUploadWithErrors,
    onSelectFile,
    onRemoveFile,
  }
}
