export const getMetricsCards = (testValues: number[], trainingValues: number[]) => {
  const titles = ['Balanced accuracy', 'Precision', 'Recall', 'F1 score']

  return titles.map((title, index) => ({
    title,
    items: [{ value: testValues[index] }, { value: trainingValues[index] }],
  }))
}

export const toPercent = (float: number) => Number((float * 100).toFixed())

export const fixNumber = (float: number, decimals: number) => Number(float.toFixed(decimals))

export const convertObjectToCsvBlob = (data: object): Blob => {
  const headers = Object.keys(data)

  const rows = []
  const maxLength = Math.max(...headers.map((key) => (data[key as keyof typeof data] as []).length))
  for (let i = 0; i < maxLength; i++) {
    const row = headers.map((header) => data[header as keyof typeof data][i] ?? '')
    rows.push(row)
  }

  const csvContent = [headers.join(','), ...rows.map((row) => row.join(','))].join('\n')
  return new Blob([csvContent], { type: 'text/csv;charset=utf-8;' })
}
