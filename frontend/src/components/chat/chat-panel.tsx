import { useState, useCallback, useRef, useEffect } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { SessionList } from './session-list'
import { MessageList } from './message-list'
import { MessageInput } from './message-input'
import { ModelProviderBadge } from './model-provider-badge'
import { useCreateChatSession, streamChatMessage } from '@/hooks/use-chat'
import { useNotificationStore } from '@/stores/notification-store'

export function ChatPanel() {
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null)
  const [streamingContent, setStreamingContent] = useState<string | null>(null)
  const [sending, setSending] = useState(false)
  const createSession = useCreateChatSession()
  const queryClient = useQueryClient()
  const notify = useNotificationStore((s) => s.addNotification)
  const abortRef = useRef<AbortController | null>(null)

  // Abort any in-flight stream on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort()
    }
  }, [])

  const handleSend = useCallback(
    async (content: string) => {
      let sessionId = activeSessionId

      if (!sessionId) {
        try {
          const session = await createSession.mutateAsync(undefined)
          if (!session) return
          sessionId = session.chat_session_id
          setActiveSessionId(sessionId)
        } catch {
          notify('error', '创建会话失败')
          return
        }
      }

      // Abort previous stream if still in flight
      abortRef.current?.abort()
      const controller = new AbortController()
      abortRef.current = controller

      setSending(true)
      setStreamingContent('')

      try {
        await streamChatMessage(
          sessionId,
          content,
          (chunk) => {
            setStreamingContent((prev) => (prev ?? '') + chunk)
          },
          controller.signal,
        )
      } catch (err) {
        if (controller.signal.aborted) return // silently ignore abort
        notify('error', err instanceof Error ? err.message : '发送失败')
      } finally {
        if (abortRef.current === controller) {
          abortRef.current = null
        }
        setStreamingContent(null)
        setSending(false)
        queryClient.invalidateQueries({ queryKey: ['chat', 'sessions', sessionId, 'messages'] })
      }
    },
    [activeSessionId, createSession, queryClient, notify],
  )

  return (
    <div className="flex h-full overflow-hidden rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
      <SessionList activeSessionId={activeSessionId} onSelect={setActiveSessionId} />
      <div className="flex flex-1 flex-col">
        <div className="flex items-center justify-between border-b border-[var(--color-border)] px-4 py-2">
          <span className="text-sm font-medium text-[var(--color-text)]">
            {activeSessionId ? '对话' : '选择或创建对话'}
          </span>
          <ModelProviderBadge />
        </div>
        {activeSessionId ? (
          <>
            <MessageList sessionId={activeSessionId} streamingContent={streamingContent} />
            <MessageInput onSend={handleSend} disabled={sending} />
          </>
        ) : (
          <div className="flex flex-1 items-center justify-center text-sm text-[var(--color-text-muted)]">
            点击左侧 + 创建新对话开始
          </div>
        )}
      </div>
    </div>
  )
}
