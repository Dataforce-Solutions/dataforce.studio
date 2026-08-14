<template>
  <div class="h-full flex flex-col">
    <header
      class="flex items-center gap-4 pb-3 border-b border-surface-200 dark:border-surface-700"
    >
      <div>
        <p class="text-xs text-muted-color">
          {{ sourceMode === 'live' ? liveSession?.branch : session.projectName }}
        </p>
        <h2 class="font-medium">
          {{ sourceMode === 'live' ? (liveSession?.name ?? 'Connecting…') : session.name }}
        </h2>
      </div>

      <nav v-if="sourceMode === 'fixture'" class="flex gap-1 ml-4">
        <RouterLink
          v-for="concept in concepts"
          :key="concept.path"
          :to="concept.path"
          class="px-3 py-1 rounded text-sm border"
          :class="
            route.path === concept.path
              ? 'border-primary-500 text-primary-600 dark:text-primary-400'
              : 'border-transparent text-muted-color hover:border-surface-300 dark:hover:border-surface-600'
          "
        >
          {{ concept.label }}
        </RouterLink>
      </nav>

      <div class="ml-auto flex items-center gap-3">
        <select
          v-model="sourceMode"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-sm"
        >
          <option value="fixture">Fixtures</option>
          <option value="live">Live daemon</option>
        </select>
        <select
          v-if="sourceMode === 'fixture'"
          v-model="fixtureId"
          class="bg-transparent border border-surface-300 dark:border-surface-600 rounded px-2 py-1 text-sm"
        >
          <option v-for="entry in fixtures" :key="entry.id" :value="entry.id">
            {{ entry.label }}
          </option>
        </select>
        <div v-if="sourceMode === 'fixture'" class="flex -space-x-1.5">
          <span
            v-for="agent in Object.values(session.agents)"
            :key="agent.agentId"
            class="w-6 h-6 rounded-full border-2 border-surface-0 dark:border-surface-900 flex items-center justify-center text-[10px] text-white"
            :style="{ background: agent.color }"
            :title="`${agent.label} — ${agent.activeBranchId ?? 'idle'}`"
          >
            {{ agent.label.slice(0, 2) }}
          </span>
        </div>
      </div>
    </header>

    <FlowConnectForm
      v-if="sourceMode === 'live'"
      :initial-base-url="connectionBaseUrl"
      :initial-token="connectionToken"
      :busy="connecting"
      :connected="liveClient !== null && liveSession !== null"
      :error="liveError"
      :error-kind="liveErrorKind"
      @connect="connectLive"
    />

    <p v-if="sourceMode === 'fixture'" class="text-xs text-muted-color py-2">
      {{ activeFixture?.description }}
    </p>
    <p v-else-if="liveSession" class="text-xs text-muted-color py-2">
      Live at journal step {{ liveSession?.step ?? '…' }}. Staleness is computed by the daemon.
    </p>

    <div class="flex-1 min-h-0 overflow-auto">
      <LiveFlowSession
        v-if="sourceMode === 'live' && liveState && liveClient"
        :state="liveState"
        :client="liveClient"
      />
      <div v-else-if="sourceMode === 'live'" class="p-4 text-sm text-muted-color">
        {{
          connecting ? 'Waiting for the daemon session…' : 'Enter daemon coordinates to connect.'
        }}
      </div>
      <RouterView v-else :key="fixtureId" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { FlowConnectionError, FlowSessionClient, type FlowConnectionErrorKind } from './api/client'
import { LiveSessionModel, type LiveSessionState } from './api/liveSession'
import FlowConnectForm, { type LiveConnection } from './components/FlowConnectForm.vue'
import LiveFlowSession from './components/LiveFlowSession.vue'
import { useWorkspace } from './composables/useWorkspace'

const route = useRoute()
const { fixtureId, fixtures, session } = useWorkspace()
const queryValue = (value: unknown): string => (typeof value === 'string' ? value : '')
const liveBaseUrl = computed(() => queryValue(route.query.live))
const liveToken = computed(() => queryValue(route.query.token))
const sourceMode = ref<'fixture' | 'live'>(liveBaseUrl.value ? 'live' : 'fixture')
const connectionBaseUrl = ref(liveBaseUrl.value)
const connectionToken = ref(liveToken.value)
const liveState = ref<LiveSessionState | null>(null)
const liveSession = computed(() => liveState.value?.snapshot ?? null)
const liveError = ref('')
const liveErrorKind = ref<FlowConnectionErrorKind | 'unknown' | ''>('')
const liveClient = shallowRef<FlowSessionClient | null>(null)
const connecting = ref(false)
let liveModel: LiveSessionModel | null = null
let connectionGeneration = 0

const stopLive = (): void => {
  connectionGeneration += 1
  liveModel?.close()
  liveModel = null
  liveClient.value?.disconnect()
  liveClient.value = null
  connecting.value = false
}

const showLiveError = (error: unknown): void => {
  liveError.value = error instanceof Error ? error.message : String(error)
  liveErrorKind.value = error instanceof FlowConnectionError ? error.kind : 'unknown'
}

const connectLive = async (connection: LiveConnection): Promise<void> => {
  stopLive()
  const generation = connectionGeneration
  connectionBaseUrl.value = connection.baseUrl
  connectionToken.value = connection.token
  liveState.value = null
  liveError.value = ''
  liveErrorKind.value = ''
  if (!connection.baseUrl || !connection.token) {
    liveError.value = 'Enter both the daemon URL and token.'
    liveErrorKind.value = 'invalid-url'
    return
  }

  connecting.value = true
  const client = new FlowSessionClient(connection.baseUrl, connection.token)
  try {
    const model = await LiveSessionModel.connect(client, {
      change: (state) => {
        if (generation !== connectionGeneration) return
        liveState.value = state
      },
      error: (error) => {
        if (generation === connectionGeneration) showLiveError(error)
      },
    })
    if (generation !== connectionGeneration) {
      model.close()
      client.disconnect()
      return
    }
    liveModel = model
    liveState.value = model.state
    liveClient.value = client
    liveError.value = ''
    liveErrorKind.value = ''
  } catch (error) {
    if (generation === connectionGeneration) showLiveError(error)
  } finally {
    if (generation === connectionGeneration) connecting.value = false
  }
}

watch(sourceMode, (mode) => {
  if (mode === 'live' && connectionBaseUrl.value && connectionToken.value) {
    void connectLive({ baseUrl: connectionBaseUrl.value, token: connectionToken.value })
  } else stopLive()
})
onMounted(() => {
  if (sourceMode.value === 'live' && connectionBaseUrl.value && connectionToken.value) {
    void connectLive({ baseUrl: connectionBaseUrl.value, token: connectionToken.value })
  }
})
onBeforeUnmount(stopLive)

const activeFixture = computed(() => fixtures.find((entry) => entry.id === fixtureId.value))

const concepts = [
  { path: '/flow/railroad', label: '1 · Canvas + railroad' },
  { path: '/flow/compare', label: '2 · Compare & compose' },
  { path: '/flow/catchup', label: '3 · Catch-up first' },
]
</script>
