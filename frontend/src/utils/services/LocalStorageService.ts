import type { LocalStorageProviderSettings } from "./LocalStorageService.interfaces"

class LocalStorageServiceClass {
  private providerSettings = 'dataforce.providersSettings';

  public getProviderSettings(): LocalStorageProviderSettings {
    const data = localStorage.getItem(this.providerSettings)
    if (!data) return {}
    else return JSON.parse(data)
  }

  public setProviderSettings(settings: LocalStorageProviderSettings) {
    localStorage.setItem(this.providerSettings, JSON.stringify(settings))
  }
}

export const LocalStorageService = new LocalStorageServiceClass()
