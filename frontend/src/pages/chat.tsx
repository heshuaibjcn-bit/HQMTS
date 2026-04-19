import { ChatPanel } from '@/components/chat/chat-panel'

export function ChatPage() {
  return (
    <div className="flex h-[calc(100vh-8rem)] flex-col">
      <h1 className="mb-4 text-xl font-semibold text-[var(--color-text)]">AI 助手</h1>
      <div className="flex-1">
        <ChatPanel />
      </div>
    </div>
  )
}
