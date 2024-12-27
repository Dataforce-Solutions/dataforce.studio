import { WebworkerMessage, type PredictRequestData, type TaskPayload } from './interfaces'

class DataProcessingWorkerClass {
  private callbacks: Function[] = []
  private callbackId: number = 1

  constructor() {}

  async sendMessage(message: WebworkerMessage, payload?: object): Promise<any> {
    const callbackId = this.callbackId++
    return new Promise((resolve, reject) => {
      this.callbacks[callbackId] = (response: any) => {
        resolve(response)
      }
      window.pyodideWorker.postMessage({
        message: message,
        id: callbackId,
        payload: payload,
      })
    })
  }

  async initPyodide() {
    if (window.pyodideStartedLoading) {
      return false
    }
    window.pyodideStartedLoading = true
    window.pyodideWorker = new Worker('/webworker.js')
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

  async startTraining(data: TaskPayload) {
    this.checkPyodideReady()

    const result = await this.sendMessage(WebworkerMessage.TABULAR_TRAIN, data)
    return result
  }

  async startPredict(data: PredictRequestData) {
    this.checkPyodideReady()

    const predictResult = await this.sendMessage(WebworkerMessage.TABULAR_PREDICT, data)
    return predictResult
  }

  async deallocateModels(models: string[]) {
    const promises = models.map((model) =>
      this.sendMessage(WebworkerMessage.TABULAR_DEALLOCATE, {
        model_id: model,
      }),
    )

    return Promise.all(promises)
  }
}

export const DataProcessingWorker = new DataProcessingWorkerClass()
