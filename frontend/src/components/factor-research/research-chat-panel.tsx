import { useState, useCallback, useRef, useEffect, useMemo } from 'react'
import { streamResearchMessage } from '@/hooks/use-factor-research'
import { useNotificationStore } from '@/stores/notification-store'
import { HypothesisCard } from './hypothesis-card'
import { TrialResultCard } from './trial-result-card'
import { Send, Loader2, Bot, User, AlertTriangle } from 'lucide-react'
import type { ResearchContext } from '@/pages/research/factor-research'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
}

const SLASH_COMMANDS = [
  { cmd: '/analyze', desc: '深度分析当前因子数据' },
  { cmd: '/hypothesis', desc: '生成新的研究假设' },
  { cmd: '/correlate', desc: '因子相关性分析' },
  { cmd: '/regime', desc: '市场状态识别' },
  { cmd: '/report', desc: '生成结构化研究报告' },
]

/** Parse structured blocks from AI response. */
function parseStructuredBlocks(content: string) {
  const blocks: Array<{ type: string; content: string }> = []
  const regex = /\[(HYPOTHESIS|TEST_RESULT|RISK_WARNING|REGIME)\]([\s\S]*?)(?=\[(?:HYPOTHESIS|TEST_RESULT|RISK_WARNING|REGIME)\]|$)/g
  let match
  while ((match = regex.exec(content)) !== null) {
    blocks.push({ type: match[1], content: match[2].trim() })
  }
  return blocks
}

/** Remove structured blocks from plain text. */
function stripStructuredBlocks(content: string): string {
  return content
    .replace(/\[(HYPOTHESIS|TEST_RESULT|RISK_WARNING|REGIME)\][\s\S]*?(?=\[(?:HYPOTHESIS|TEST_RESULT|RISK_WARNING|REGIME)\]|$)/g, '')
    .trim()
}

interface ResearchChatPanelProps {
  context?: ResearchContext
}

export function ResearchChatPanel({ context }: ResearchChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [sending, setSending] = useState(false)
  const [streaming, setStreaming] = useState<string | null>(null)
  const [showCommands, setShowCommands] = useState(false)
  const notify = useNotificationStore((s) => s.addNotification)
  const abortRef = useRef<AbortController | null>(null)
  const scrollRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    return () => { abortRef.current?.abort() }
  }, [])

  // Auto-scroll on new content
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight
    }
  }, [messages, streaming])

  const handleSend = useCallback(async (content: string) => {
    if (!content.trim() || sending) return

    const userMsg: Message = { id: `u_${Date.now()}`, role: 'user', content }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setShowCommands(false)

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    setSending(true)
    setStreaming('')

    try {
      await streamResearchMessage(
        content,
        context ? { instruments: context.instruments, factors: context.factors, time_range: context.timeRange } : undefined,
        (chunk) => {
          setStreaming((prev) => (prev ?? '') + chunk)
        },
        controller.signal,
      )
    } catch (err) {
      if (controller.signal.aborted) return
      notify('error', err instanceof Error ? err.message : '发送失败')
    } finally {
      if (abortRef.current === controller) {
        abortRef.current = null
      }
      // Move streaming to final message
      setStreaming((prev) => {
        if (prev) {
          const assistantMsg: Message = { id: `a_${Date.now()}`, role: 'assistant', content: prev }
          setMessages((prevMsgs) => [...prevMsgs, assistantMsg])
        }
        return null
      })
      setSending(false)
    }
  }, [sending, notify])

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend(input)
    }
  }

  const handleInputChange = (val: string) => {
    setInput(val)
    setShowCommands(val.startsWith('/') && !val.includes(' '))
  }

  const filteredCommands = useMemo(
    () => (showCommands ? SLASH_COMMANDS.filter((c) => c.cmd.startsWith(input)) : []),
    [showCommands, input],
  )

  const allMessages = useMemo(() => {
    const msgs = [...messages]
    if (streaming) {
      msgs.push({ id: 'streaming', role: 'assistant', content: streaming })
    }
    return msgs
  }, [messages, streaming])

  return (
    <div className="flex h-[600px] flex-col rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)]">
      {/* Header */}
      <div className="flex items-center gap-2 border-b border-[var(--color-border)] px-4 py-2">
        <Bot className="h-4 w-4 text-[var(--color-primary)]" />
        <span className="text-sm font-medium text-[var(--color-text)]">AI 研究助手</span>
        <span className="text-xs text-[var(--color-text-muted)]">
          支持 /analyze /hypothesis /correlate /regime /report 命令
        </span>
      </div>

      {/* Context bar (PRD 12.3.4) */}
      {context && (context.instruments.length > 0 || context.factors.length > 0 || context.timeRange) && (
        <div className="flex flex-wrap items-center gap-2 border-b border-[var(--color-border)] bg-[var(--color-bg-tertiary)] px-4 py-1.5 text-[10px]">
          {context.instruments.length > 0 && (
            <span className="text-[var(--color-text-secondary)]">
              标的: <span className="font-mono text-[var(--color-text)]">{context.instruments.join(', ')}</span>
            </span>
          )}
          {context.factors.length > 0 && (
            <span className="text-[var(--color-text-secondary)]">
              因子: <span className="font-mono text-[var(--color-text)]">{context.factors.join(', ')}</span>
            </span>
          )}
          {context.timeRange && (
            <span className="text-[var(--color-text-secondary)]">
              时间: <span className="text-[var(--color-text)]">{context.timeRange}</span>
            </span>
          )}
        </div>
      )}

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-4 space-y-4">
        {allMessages.length === 0 && (
          <div className="flex h-full items-center justify-center text-sm text-[var(--color-text-muted)]">
            向 AI 研究助手提问，或使用斜杠命令开始分析
          </div>
        )}
        {allMessages.map((msg) => (
          <div key={msg.id} className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            {msg.role === 'assistant' && (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-primary)]">
                <Bot className="h-4 w-4 text-white" />
              </div>
            )}
            <div className={`max-w-[80%] space-y-2 rounded-lg px-3 py-2 text-sm ${
              msg.role === 'user'
                ? 'bg-[var(--color-primary)] text-white'
                : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text)]'
            }`}>
              {/* Plain text part */}
              <div className="whitespace-pre-wrap">{stripStructuredBlocks(msg.content)}</div>
              {/* Structured blocks */}
              {parseStructuredBlocks(msg.content).map((block, idx) => {
                if (block.type === 'HYPOTHESIS') {
                  return <HypothesisCard key={idx} content={block.content} />
                }
                if (block.type === 'TEST_RESULT') {
                  return <TrialResultCard key={idx} content={block.content} />
                }
                if (block.type === 'RISK_WARNING') {
                  return (
                    <div key={idx} className="flex items-start gap-2 rounded border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                      <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
                      <span>{block.content}</span>
                    </div>
                  )
                }
                if (block.type === 'REGIME') {
                  return (
                    <div key={idx} className="rounded border border-blue-200 bg-blue-50 px-3 py-2 text-sm text-blue-700">
                      {block.content}
                    </div>
                  )
                }
                return null
              })}
            </div>
            {msg.role === 'user' && (
              <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-[var(--color-bg-tertiary)]">
                <User className="h-4 w-4 text-[var(--color-text-secondary)]" />
              </div>
            )}
          </div>
        ))}
        {sending && !streaming && (
          <div className="flex gap-3">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--color-primary)]">
              <Loader2 className="h-4 w-4 animate-spin text-white" />
            </div>
            <div className="rounded-lg bg-[var(--color-bg-tertiary)] px-3 py-2 text-sm text-[var(--color-text-muted)]">
              思考中...
            </div>
          </div>
        )}
      </div>

      {/* Slash command dropdown */}
      {filteredCommands.length > 0 && (
        <div className="border-t border-[var(--color-border)] bg-[var(--color-bg)] px-4 py-1">
          {filteredCommands.map((c) => (
            <button
              key={c.cmd}
              onClick={() => {
                setInput(c.cmd + ' ')
                setShowCommands(false)
                inputRef.current?.focus()
              }}
              className="flex w-full items-center gap-2 rounded px-2 py-1 text-xs hover:bg-[var(--color-bg-tertiary)]"
            >
              <span className="font-mono text-[var(--color-primary)]">{c.cmd}</span>
              <span className="text-[var(--color-text-muted)]">{c.desc}</span>
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="border-t border-[var(--color-border)] px-4 py-2">
        <div className="flex items-center gap-2">
          <input
            ref={inputRef}
            type="text"
            placeholder="输入问题或 / 命令..."
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={sending}
            className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-1.5 text-sm text-[var(--color-text)] outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
          />
          <button
            onClick={() => handleSend(input)}
            disabled={sending || !input.trim()}
            className="flex items-center justify-center rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-white transition-colors hover:opacity-90 disabled:opacity-50"
          >
            {sending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </div>
  )
}
