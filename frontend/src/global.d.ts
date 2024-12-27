export {}

declare global {
  interface Window {
    pyodideWorker: Worker
    pyodideStartedLoading: boolean
  }
}
