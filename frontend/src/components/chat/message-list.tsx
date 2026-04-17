import { useEffect, useRef } from 'react'
import { useChatMessages } from '@/hooks/use-chat'
import { MessageBubble } from './message-bubble'
import { ApprovalCard } from './approval-card'
import type { Approval } from '@/hooks/use-approvals'

interface Props {
  sessionId: string
  streamingContent: string | null
}

function extractApprovals(metadataJson: string | null): Approval[] {
  if (!metadataJson) return []
  try {
    const parsed = JSON.parse(metadataJson)
    if (parsed.approvals && Array.isArray(parsed.approvals)) {
      return parsed.approvals
    }
  } catch {
    // ignore
  }
  return []
}

export function MessageList({ sessionId, streamingContent }: Props) {
  const { data: messages } = useChatMessages(sessionId)
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, streamingContent])

  return (
    <div className="flex-1 overflow-auto p-4">
      <div className="space-y-3">
        {messages?.map((msg) => {
          const approvals = msg.role === 'assistant' ? extractApprovals(msg.metadata_json) : []
          return (
            <div key={msg.chat_message_id} className="space-y-2">
              <MessageBubble role={msg.role} content={msg.content} />
              {approvals.map((approval) => (
                <ApprovalCard key={approval.proposal_id} approval={approval} />
              ))}
            </div>
          )
        })}
        {streamingContent && (
          <MessageBubble role="assistant" content={streamingContent} />
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
