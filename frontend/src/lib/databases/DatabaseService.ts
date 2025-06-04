import type { DatabaseMetadata, DataforceFile, Notebook } from './database.interfaces'
import { openDB, deleteDB, type IDBPDatabase } from 'idb'
import jszip from 'jszip'
import { saveAs } from 'file-saver'

const DATABASE_PREFIX = 'jl_'
const FILES_STORE = 'files'
const DATAFORCE_FILES_EXTENSIONS = ['.dfs', '.fnnx', '.pyfnx']

class DatabaseServiceClass {
  async getDatabases() {
    if (!indexedDB.databases) {
      console.warn('indexedDB.databases() not supported')
      return []
    }
    return await indexedDB.databases()
  }

  async deleteDatabase(name: string) {
    await deleteDB(name, {
      blocked: () => {
        console.warn(`db ${name} blocked`)
      },
    })
  }

  async createDatabase(id: string, metadata: DatabaseMetadata) {
    const db = await openDB(DATABASE_PREFIX + id, 1, {
      upgrade(db) {
        db.createObjectStore('meta')
      },
    })
    await db.put('meta', metadata, 'info')
    db.close()
    return db
  }

  async getDatabaseInfo(name: string): Promise<Notebook> {
    let db = await openDB(name)
    if (db.objectStoreNames.contains('meta')) {
      const meta = await db.get('meta', 'info')
      const files = await this.getDataforceFiles(db)
      const info = { name, version: db.version, ...meta, files }
      db.close()
      return info
    }
    const version = db.version
    db.close()
    db = await openDB(name, version + 1, {
      upgrade(upgradeDb) {
        if (!upgradeDb.objectStoreNames.contains('meta')) {
          upgradeDb.createObjectStore('meta')
        }
      },
    })
    db.close()
    return { name, version: db.version }
  }

  async getDatabasesWithMetadata(): Promise<Notebook[]> {
    const databases = await this.getDatabases()
    const filteredDatabases = databases.filter(
      (database) => database.name && database.name.startsWith(DATABASE_PREFIX),
    )
    const promises = filteredDatabases.map(async (database) => {
      if (!database.name) return database as Notebook
      const metadata = await DatabaseService.getDatabaseInfo(database.name)
      return { ...database, ...metadata }
    })
    return Promise.all(promises)
  }

  async editDatabase(name: string, metadata: DatabaseMetadata) {
    const version = await this.getVersion(name)
    const db = await openDB(name, version + 1, {
      upgrade(db) {
        if (!db.objectStoreNames.contains('meta')) {
          db.createObjectStore('meta')
        }
      },
    })
    await db.put('meta', metadata, 'info')
    db.close()
  }

  async createBackup(name: string) {
    const db = await openDB(name)
    const metadata = await this.getDatabaseInfo(name)
    const databaseName = metadata?.fullname || name
    if (!db.objectStoreNames.contains(FILES_STORE)) {
      db.close()
      throw new Error(`Database ${databaseName} not includes ${FILES_STORE} store`)
    }
    const tx = db.transaction(FILES_STORE, 'readonly')
    const store = tx.objectStore(FILES_STORE)
    const allFiles = await store.getAll()
    const zip = new jszip()
    for (const file of allFiles) {
      const fileName = file.name || file.path
      const content = file.content || file.data || ''
      const format = file?.format
      if (!fileName || !content) continue
      let serializedContent: string | Blob
      if (format === 'json') {
        try {
          serializedContent = JSON.stringify(content, null, 2)
        } catch (e) {
          console.error('Failed to serialize file data')
          continue
        }
      } else if (format === 'text') {
        serializedContent = content
      } else {
        continue
      }
      zip.file(fileName, serializedContent)
    }
    const zipBlob = await zip.generateAsync({ type: 'blob' })
    saveAs(zipBlob, `${databaseName}-backup.zip`)
    db.close()
  }

  private async getVersion(name: string) {
    const databases = await indexedDB.databases()
    const found = databases.find((db) => db.name === name)
    return found?.version ?? 0
  }

  private async getDataforceFiles(db: IDBPDatabase): Promise<DataforceFile[]> {
    if (!db.objectStoreNames.contains(FILES_STORE)) return []
    const tx = db.transaction(FILES_STORE, 'readonly')
    const store = tx.objectStore(FILES_STORE)
    const allFiles = await store.getAll()
    const files = allFiles.filter((file) => {
      return DATAFORCE_FILES_EXTENSIONS.find((extension) => {
        if (typeof file?.name === 'string' && file?.name.endsWith(extension)) return true
        if (typeof file?.path === 'string' && file?.path.endsWith(extension)) return true
        return false
      })
    })
    return files
  }
}

export const DatabaseService = new DatabaseServiceClass()
