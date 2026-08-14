import type {
  AssetPage,
  JournalMessage,
  JournalStreamMessage,
  JsonValue,
  KernelMessage,
  LiveSessionSnapshot,
  RunLogMessage,
} from './types'

export interface EventSourceLike {
  onmessage: ((event: MessageEvent<string>) => void) | null
  onerror: (() => void) | null
  close(): void
}

export type EventSourceFactory = (url: string) => EventSourceLike

export interface JournalHandlers {
  transaction?(message: JournalMessage): void
  kernel?(message: KernelMessage): void
  error?(error: Error): void
}

export interface StreamSubscription {
  close(): void
}

export interface FlowSessionClientOptions {
  fetch?: typeof fetch
  eventSource?: EventSourceFactory
  reconnectDelayMs?: number
  requestTimeoutMs?: number
}

export type FlowConnectionErrorKind = 'invalid-url' | 'unauthorized' | 'unreachable' | 'request'

export class FlowConnectionError extends Error {
  constructor(
    readonly kind: FlowConnectionErrorKind,
    message: string,
    readonly status: number | null = null,
  ) {
    super(message)
    this.name = 'FlowConnectionError'
  }
}

export class FlowRpcError extends Error {
  constructor(
    readonly code: number,
    message: string,
    readonly data: JsonValue,
    readonly status: number,
  ) {
    super(message)
    this.name = 'FlowRpcError'
  }
}

export class FlowSessionClient {
  private readonly fetcher: typeof fetch
  private readonly eventSourceFactory: EventSourceFactory
  private readonly reconnectDelayMs: number
  private readonly requestTimeoutMs: number
  private journalSource: EventSourceLike | null = null
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null
  private stopped = true
  private handlers: JournalHandlers = {}
  private cursor = 0

  constructor(
    private readonly baseUrl: string,
    private readonly token: string,
    options: FlowSessionClientOptions = {},
  ) {
    // Wrap the global fetch: calling it as `this.fetcher(...)` would rebind
    // its receiver to the client and throw "Illegal invocation" in browsers.
    this.fetcher = options.fetch ?? ((input, init) => fetch(input, init))
    this.eventSourceFactory =
      options.eventSource ?? ((url: string) => new EventSource(url) as EventSourceLike)
    this.reconnectDelayMs = options.reconnectDelayMs ?? 500
    this.requestTimeoutMs = options.requestTimeoutMs ?? 5_000
  }

  async snapshot(): Promise<LiveSessionSnapshot> {
    return this.requestJson<LiveSessionSnapshot>(
      '/api/session',
      {},
      'Live session request',
      false,
      this.requestTimeoutMs,
    )
  }

  async rpc<Result extends JsonValue = JsonValue>(
    method: string,
    params: Record<string, JsonValue> = {},
  ): Promise<Result> {
    return this.requestJson<Result>(
      '/api/rpc',
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ method, params }),
      },
      'Daemon RPC request',
      true,
    )
  }

  async assetPage(
    target: string,
    query: Record<string, JsonValue> = { offset: 0, limit: 100 },
  ): Promise<AssetPage> {
    const separator = target.indexOf('.')
    const slug = target.slice(0, separator)
    const output = target.slice(separator + 1)
    if (separator < 1 || !output) throw new Error('asset target must be slug.output')
    return this.requestJson<AssetPage>(
      `/api/assets/${encodeURIComponent(slug)}/${encodeURIComponent(output)}/page`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify(query),
      },
      'Asset page request',
    )
  }

  async editParams(
    slug: string,
    params: Record<string, JsonValue>,
    baseDefinitionHash: string,
  ): Promise<Record<string, JsonValue>> {
    return this.requestJson<Record<string, JsonValue>>(
      `/api/cells/${encodeURIComponent(slug)}/params`,
      {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ params, base_definition_hash: baseDefinitionHash }),
      },
      'Parameter edit',
    )
  }

  connect(handlers: JournalHandlers, cursor = 0): StreamSubscription {
    this.disconnect()
    this.handlers = handlers
    this.cursor = cursor
    this.stopped = false
    this.openJournal()
    return { close: () => this.disconnect() }
  }

  subscribeRunLogs(runId: string, handler: (message: RunLogMessage) => void): StreamSubscription {
    const source = this.eventSourceFactory(this.url(`/logs/${encodeURIComponent(runId)}`))
    source.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as RunLogMessage
        if (message.channel === 'run-log' && message.run_id === runId) handler(message)
      } catch (error) {
        this.handlers.error?.(asError(error))
      }
    }
    source.onerror = () => source.close()
    return { close: () => source.close() }
  }

  disconnect(): void {
    this.stopped = true
    this.journalSource?.close()
    this.journalSource = null
    if (this.reconnectTimer !== null) clearTimeout(this.reconnectTimer)
    this.reconnectTimer = null
  }

  private openJournal(): void {
    const source = this.eventSourceFactory(this.url('/events', { cursor: String(this.cursor) }))
    this.journalSource = source
    source.onmessage = (event) => this.receiveJournal(event.data)
    source.onerror = () => {
      source.close()
      if (this.stopped) return
      this.reconnectTimer = setTimeout(() => this.openJournal(), this.reconnectDelayMs)
    }
  }

  private receiveJournal(raw: string): void {
    try {
      const message = JSON.parse(raw) as JournalStreamMessage
      if (message.kind === 'transaction') {
        if (message.cursor <= this.cursor) return
        this.cursor = message.cursor
        this.handlers.transaction?.(message)
      } else if (message.kind === 'kernel') {
        this.handlers.kernel?.(message)
      }
    } catch (error) {
      this.handlers.error?.(asError(error))
    }
  }

  private async requestJson<Result>(
    path: string,
    options: RequestInit,
    label: string,
    rpc = false,
    timeoutMs: number | null = null,
  ): Promise<Result> {
    const controller = timeoutMs === null ? null : new AbortController()
    const timeout =
      controller === null || timeoutMs === null
        ? null
        : setTimeout(() => controller.abort(), timeoutMs)
    try {
      const response = await this.fetcher(this.url(path), {
        ...options,
        signal: controller?.signal ?? options.signal,
      })
      const body = await responseJson(response)
      if (response.ok) return body as Result
      if (response.status === 401) {
        throw new FlowConnectionError(
          'unauthorized',
          'Daemon rejected the token. Check it and try again.',
          response.status,
        )
      }
      if (rpc && isRpcErrorBody(body)) {
        throw new FlowRpcError(body.error.code, body.error.message, body.error.data, response.status)
      }
      throw new FlowConnectionError(
        'request',
        `${label} failed (${response.status})${responseDetail(body)}`,
        response.status,
      )
    } catch (error) {
      if (error instanceof TypeError || isAbortError(error)) {
        throw new FlowConnectionError(
          'unreachable',
          `Cannot reach the daemon at ${this.baseUrl}. Check that it is running and try again.`,
        )
      }
      throw error
    } finally {
      if (timeout !== null) clearTimeout(timeout)
    }
  }

  private url(path: string, params: Record<string, string> = {}): string {
    let url: URL
    try {
      url = new URL(path, `${this.baseUrl.replace(/\/$/, '')}/`)
    } catch {
      throw new FlowConnectionError('invalid-url', 'Enter a valid daemon URL, including http://.')
    }
    url.searchParams.set('token', this.token)
    for (const [name, value] of Object.entries(params)) url.searchParams.set(name, value)
    return url.toString()
  }
}

const asError = (value: unknown): Error =>
  value instanceof Error ? value : new Error(String(value))

const isAbortError = (value: unknown): boolean =>
  typeof value === 'object' && value !== null && 'name' in value && value.name === 'AbortError'

const responseJson = async (response: Response): Promise<unknown> => {
  try {
    return await response.json()
  } catch (error) {
    if (isAbortError(error)) throw error
    return null
  }
}

const isRpcErrorBody = (
  value: unknown,
): value is { error: { code: number; message: string; data: JsonValue } } => {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const error = value.error
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof error.code === 'number' &&
    'message' in error &&
    typeof error.message === 'string' &&
    'data' in error
  )
}

const responseDetail = (value: unknown): string => {
  if (typeof value !== 'object' || value === null || !('detail' in value)) return ''
  return typeof value.detail === 'string' ? `: ${value.detail}` : ''
}
