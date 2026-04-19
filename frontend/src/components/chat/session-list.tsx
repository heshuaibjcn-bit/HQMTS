import { useChatSessions, useCreateChatSession, useDeleteChatSession } from '@/hooks/use-chat'
import { Plus, Trash2 } from 'lucide-react'

interface Props {
  activeSessionId: string | null
  onSelect: (sessionId: string) => void
}

export function SessionList({ activeSessionId, onSelect }: Props) {
  const { data: sessions } = useChatSessions()
  const createSession = useCreateChatSession()
  const deleteSession = useDeleteChatSession()

  const handleCreate = async () => {
    const session = await createSession.mutateAsync('新对话')
    if (session) onSelect(session.chat_session_id)
  }

  const handleDelete = async (sessionId: string) => {
    await deleteSession.mutateAsync(sessionId)
  }

  return (
    <div className="flex h-full w-56 flex-col border-r border-[var(--color-border)] bg-[var(--color-bg)]">
      <div className="flex items-center justify-between border-b border-[var(--color-border)] p-3">
        <span className="text-sm font-medium text-[var(--color-text)]">对话</span>
        <button
          onClick={handleCreate}
          disabled={createSession.isPending}
          className="rounded p-1 text-[var(--color-text-muted)] hover:bg-[var(--color-bg-tertiary)]"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
      <div className="flex-1 overflow-auto p-2">
        {sessions?.map((session) => (
          <div
            key={session.chat_session_id}
            onClick={() => onSelect(session.chat_session_id)}
            className={`group flex cursor-pointer items-center justify-between rounded-md px-2 py-1.5 text-sm ${
              activeSessionId === session.chat_session_id
                ? 'bg-[var(--color-primary)] text-white'
                : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]'
            }`}
          >
            <span className="truncate">{session.title || '新对话'}</span>
            <button
              onClick={(e) => {
                e.stopPropagation()
                handleDelete(session.chat_session_id)
              }}
              className="shrink-0 rounded p-0.5 opacity-0 group-hover:opacity-100"
            >
              <Trash2 className="h-3 w-3" />
            </button>
          </div>
        ))}
        {(!sessions || sessions.length === 0) && (
          <p className="px-2 py-4 text-center text-xs text-[var(--color-text-muted)]">
            暂无对话，点击 + 创建
          </p>
        )}
      </div>
    </div>
  )
}
