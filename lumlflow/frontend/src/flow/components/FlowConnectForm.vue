<template>
  <section
    data-live-connect
    class="my-3 rounded-lg border border-surface-200 dark:border-surface-700 p-4"
  >
    <div class="flex items-center justify-between gap-3 mb-3">
      <div>
        <h3 class="font-medium">Connect to a flow daemon</h3>
        <p class="text-xs text-muted-color">Paste the coordinates printed by flow daemon start.</p>
      </div>
      <span v-if="connected" class="text-xs text-green-700 dark:text-green-400">Connected</span>
    </div>

    <form
      class="grid gap-3 md:grid-cols-[minmax(16rem,1fr)_minmax(12rem,1fr)_auto]"
      @submit.prevent="submit"
    >
      <label class="grid gap-1 text-xs text-muted-color">
        Daemon URL
        <input
          v-model="baseUrl"
          name="daemon-url"
          type="url"
          required
          placeholder="http://127.0.0.1:8765"
          class="rounded border border-surface-300 dark:border-surface-600 bg-transparent px-3 py-2 text-sm text-color"
        />
      </label>
      <label class="grid gap-1 text-xs text-muted-color">
        Token
        <input
          v-model="token"
          name="daemon-token"
          type="password"
          required
          autocomplete="off"
          class="rounded border border-surface-300 dark:border-surface-600 bg-transparent px-3 py-2 text-sm text-color"
        />
      </label>
      <button
        type="submit"
        :disabled="busy"
        class="self-end rounded bg-primary-600 px-4 py-2 text-sm text-white disabled:opacity-50"
      >
        {{ busy ? 'Connecting…' : connected ? 'Reconnect' : 'Connect' }}
      </button>
    </form>

    <label
      v-if="recentConnections.length"
      class="mt-3 flex items-center gap-2 text-xs text-muted-color"
    >
      Recent
      <select
        data-recent-connections
        class="rounded border border-surface-300 dark:border-surface-600 bg-transparent px-2 py-1 text-sm text-color"
        @change="selectRecent"
      >
        <option value="">Choose a daemon…</option>
        <option
          v-for="connection in recentConnections"
          :key="connection.baseUrl"
          :value="connection.baseUrl"
        >
          {{ connection.baseUrl }}
        </option>
      </select>
    </label>

    <p
      v-if="error"
      role="alert"
      :data-connection-error="errorKind"
      class="mt-3 text-sm text-red-600 dark:text-red-400"
    >
      {{ error }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { ref, watch } from 'vue'

export interface LiveConnection {
  baseUrl: string
  token: string
}

const RECENT_CONNECTIONS_KEY = 'lumlflow.recent-connections'
const MAX_RECENT_CONNECTIONS = 5

const props = withDefaults(
  defineProps<{
    initialBaseUrl?: string
    initialToken?: string
    busy?: boolean
    connected?: boolean
    error?: string
    errorKind?: string
  }>(),
  {
    initialBaseUrl: '',
    initialToken: '',
    busy: false,
    connected: false,
    error: '',
    errorKind: '',
  },
)
const emit = defineEmits<{ connect: [connection: LiveConnection] }>()

const baseUrl = ref(props.initialBaseUrl)
const token = ref(props.initialToken)
const recentConnections = ref(loadRecentConnections())

watch(
  () => props.initialBaseUrl,
  (value) => {
    if (value) baseUrl.value = value
  },
)
watch(
  () => props.initialToken,
  (value) => {
    if (value) token.value = value
  },
)

const submit = (): void => {
  const connection = {
    baseUrl: baseUrl.value.trim().replace(/\/$/, ''),
    token: token.value.trim(),
  }
  rememberConnection(connection)
  emit('connect', connection)
}

const selectRecent = (event: Event): void => {
  const selectedUrl = (event.target as HTMLSelectElement).value
  const connection = recentConnections.value.find(({ baseUrl }) => baseUrl === selectedUrl)
  if (!connection) return
  baseUrl.value = connection.baseUrl
  token.value = connection.token
}

const rememberConnection = (connection: LiveConnection): void => {
  const withoutDuplicate = recentConnections.value.filter(
    ({ baseUrl }) => baseUrl !== connection.baseUrl,
  )
  recentConnections.value = [connection, ...withoutDuplicate].slice(0, MAX_RECENT_CONNECTIONS)
  try {
    localStorage.setItem(RECENT_CONNECTIONS_KEY, JSON.stringify(recentConnections.value))
  } catch {
    return
  }
}

function loadRecentConnections(): LiveConnection[] {
  try {
    const stored = JSON.parse(localStorage.getItem(RECENT_CONNECTIONS_KEY) ?? '[]') as unknown
    if (!Array.isArray(stored)) return []
    return stored
      .filter(
        (value): value is LiveConnection =>
          typeof value === 'object' &&
          value !== null &&
          'baseUrl' in value &&
          typeof value.baseUrl === 'string' &&
          'token' in value &&
          typeof value.token === 'string',
      )
      .slice(0, MAX_RECENT_CONNECTIONS)
  } catch {
    return []
  }
}
</script>
