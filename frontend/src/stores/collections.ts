import type {
  OrbitCollection,
  OrbitCollectionCreator,
} from '@/lib/api/orbit-collections/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { useOrganizationStore } from './organization'
import { useOrbitsStore } from './orbits'
import { dataforceApi } from '@/lib/api'

export const useCollectionsStore = defineStore('collections', () => {
  const organizationStore = useOrganizationStore()
  const orbitsStore = useOrbitsStore()

  const collectionsList = ref<OrbitCollection[]>([])
  const currentCollection = ref<OrbitCollection | null>(null)

  const requestInfo = computed(() => {
    if (!organizationStore.currentOrganization?.id)
      throw new Error('Current organization not found')
    if (!orbitsStore.currentOrbitDetails?.id) throw new Error('Current orbit not found')
    return {
      organizationId: organizationStore.currentOrganization.id,
      orbitId: orbitsStore.currentOrbitDetails.id,
    }
  })

  async function loadCollections() {
    collectionsList.value = await dataforceApi.orbitCollections.getCollectionsList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
    )
  }

  async function createCollection(payload: OrbitCollectionCreator) {
    const collection = await dataforceApi.orbitCollections.createCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      payload,
    )
    collectionsList.value.push(collection)
  }

  async function updateCollection(collectionId: number, payload: OrbitCollectionCreator) {
    const updatedCollection = await dataforceApi.orbitCollections.updateCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
      payload,
    )
    collectionsList.value = collectionsList.value.map((collection) => {
      return collection.id === collectionId ? updatedCollection : collection
    })
  }

  async function deleteCollection(collectionId: number) {
    await dataforceApi.orbitCollections.deleteCollection(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      collectionId,
    )
    collectionsList.value = collectionsList.value.filter(
      (collection) => collection.id !== collectionId,
    )
  }

  async function setCurrentCollection(collectionId: number) {
    currentCollection.value =
      collectionsList.value.find((collection) => collection.id === collectionId) || null
  }

  function resetCurrentCollection() {
    currentCollection.value = null
  }

  function reset() {
    collectionsList.value = []
    resetCurrentCollection()
  }

  return {
    collectionsList,
    currentCollection,
    loadCollections,
    createCollection,
    updateCollection,
    deleteCollection,
    reset,
    setCurrentCollection,
    resetCurrentCollection,
  }
})
