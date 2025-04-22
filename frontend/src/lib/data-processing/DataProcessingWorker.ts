import { WEBWORKER_ROUTES_ENUM, WebworkerMessage, type PredictRequestData, type PromptOptimizationData, type TaskPayload } from './interfaces'

class DataProcessingWorkerClass {
  private callbacks: Function[] = []
  private callbackId: number = 1

  constructor() {}

  async sendMessage(message: WebworkerMessage, route?: WEBWORKER_ROUTES_ENUM, data?: any): Promise<any> {
    const callbackId = this.callbackId++
    return new Promise((resolve, reject) => {
      this.callbacks[callbackId] = (response: any) => {
        resolve(response)
      }
      const options = { message, id: callbackId, payload: { route, data } }
      window.pyodideWorker.postMessage(options)
    })
  }

  async initPyodide() {
    if (window.pyodideStartedLoading) {
      return false
    }
    window.pyodideStartedLoading = true
    window.pyodideWorker = new Worker(new URL('@/workers/webworker.js', import.meta.url), {
      type: 'module'
    })
    window.pyodideWorker.onmessage = async (event) => {
      const m = event.data
      const callback = this.callbacks[m.id]
      delete this.callbacks[m.id]
      callback(m.payload)
    }
    return true
  }

  saveModel(modelBlob: Blob, fileName: string) {
    const url = URL.createObjectURL(modelBlob)
    const a = document.createElement('a')
    a.href = url
    a.download = fileName
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  async checkPyodideReady() {
    const pyodideReady = await this.sendMessage(WebworkerMessage.LOAD_PYODIDE)
    if (!pyodideReady) throw new Error('Webworker is not ready')
  }

  async startTraining(data: TaskPayload | PromptOptimizationData, route: WEBWORKER_ROUTES_ENUM.TABULAR_TRAIN | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_TRAIN) {
    this.checkPyodideReady()
    const result = await this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, data)
    return result
  }

  async startPredict(data: PredictRequestData, route: WEBWORKER_ROUTES_ENUM.TABULAR_PREDICT | WEBWORKER_ROUTES_ENUM.PROMPT_OPTIMIZATION_PREDICT) {
    this.checkPyodideReady()
    const predictResult = await this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, data)
    return predictResult
  }

  async deallocateModels(models: string[], route: WEBWORKER_ROUTES_ENUM.TABULAR_DEALLOCATE | WEBWORKER_ROUTES_ENUM.STORE_DEALLOCATE) {
    const promises = models.map((model_id) =>
      this.sendMessage(WebworkerMessage.INVOKE_ROUTE, route, {  model_id }),
    )
    return Promise.all(promises)
  }

  async interrupt() {
    await this.sendMessage(WebworkerMessage.INTERRUPT)
  }
}

export const DataProcessingWorker = new DataProcessingWorkerClass()
