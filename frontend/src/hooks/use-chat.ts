import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { apiClient } from '@/lib/api-client'
import { useAuthStore } from '@/stores/auth-store'

export interface ChatSession {
  chat_session_id: string
  title: string
  model_provider: string
  environment: string
  created_at: string
  updated_at: string
}

export interface ChatMessage {
  chat_message_id: string
  chat_session_id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  metadata_json: string | null
  created_at: string
}

export function useChatSessions() {
  return useQuery({
    queryKey: ['chat', 'sessions'],
    queryFn: () => apiClient.get<ChatSession[]>('/chat/sessions'),
  })
}

export function useChatMessages(sessionId: string) {
  return useQuery({
    queryKey: ['chat', 'sessions', sessionId, 'messages'],
    queryFn: () =>
      apiClient.get<ChatMessage[]>(`/chat/sessions/${sessionId}/messages`),
    enabled: !!sessionId,
  })
}

export function useCreateChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (title?: string) =>
      apiClient.post<ChatSession>('/chat/sessions', { title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
    },
  })
}

export function useDeleteChatSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (sessionId: string) =>
      apiClient.delete(`/chat/sessions/${sessionId}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
    },
  })
}

const SSE_IDLE_TIMEOUT_MS = 30_000

export async function streamChatMessage(
  sessionId: string,
  content: string,
  onChunk: (chunk: string) => void,
  signal?: AbortSignal,
): Promise<void> {
  // Pre-check token, refresh if missing
  let token = useAuthStore.getState().token
  if (!token) {
    const refreshed = await apiClient.tryRefresh()
    if (!refreshed) {
      useAuthStore.getState().logout()
      throw new Error('Session expired')
    }
    token = useAuthStore.getState().token
  }

  const response = await fetch(`/chat/sessions/${sessionId}/messages`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ content }),
    signal,
  })

  if (response.status === 401) {
    // Try refresh once
    const refreshed = await apiClient.tryRefresh()
    if (!refreshed) {
      useAuthStore.getState().logout()
      throw new Error('Session expired during chat. Please retry.')
    }
    throw new Error('Session expired during chat. Please retry.')
  }

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }))
    throw new Error(err.detail || `HTTP ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) throw new Error('No response body')

  const decoder = new TextDecoder()
  let buffer = ''
  let lastActivity = Date.now()

  try {
    while (true) {
      if (signal?.aborted) throw new Error('Aborted')

      // Idle timeout check
      if (Date.now() - lastActivity > SSE_IDLE_TIMEOUT_MS) {
        throw new Error('Chat response timed out')
      }

      // Race read against a 5s poll interval for idle/abort checks
      const readPromise = reader.read()
      const timeoutPromise = new Promise<{ done: boolean; value?: undefined }>(
        (resolve) => setTimeout(() => resolve({ done: false }), 5_000),
      )

      const result = await Promise.race([readPromise, timeoutPromise])

      if (result.done) break
      if (!result.value) continue // timeout tick, loop back for idle/abort check

      lastActivity = Date.now()
      buffer += decoder.decode(result.value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6)
          if (data === '[DONE]') return
          try {
            const parsed = JSON.parse(data)
            if (parsed.content) {
              onChunk(parsed.content)
            }
          } catch {
            // skip malformed chunks
          }
        }
      }
    }
  } finally {
    reader.releaseLock()
  }
}
