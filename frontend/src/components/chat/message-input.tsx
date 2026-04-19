import { useState } from 'react'
import { Send } from 'lucide-react'

const SLASH_COMMANDS = [
  { cmd: '/backtest', desc: '运行回测' },
  { cmd: '/flatten', desc: '强制平仓' },
  { cmd: '/approve', desc: '审批操作' },
  { cmd: '/status', desc: '系统状态' },
  { cmd: '/audit', desc: '审计日志' },
  { cmd: '/help', desc: '帮助' },
]

interface Props {
  onSend: (content: string) => void
  disabled: boolean
}

export function MessageInput({ onSend, disabled }: Props) {
  const [value, setValue] = useState('')
  const [showCommands, setShowCommands] = useState(false)
  const [filteredCommands, setFilteredCommands] = useState(SLASH_COMMANDS)

  const handleChange = (v: string) => {
    setValue(v)
    if (v.startsWith('/')) {
      setShowCommands(true)
      setFilteredCommands(
        SLASH_COMMANDS.filter((c) => c.cmd.startsWith(v)),
      )
    } else {
      setShowCommands(false)
    }
  }

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!value.trim() || disabled) return
    onSend(value.trim())
    setValue('')
    setShowCommands(false)
  }

  const selectCommand = (cmd: string) => {
    setValue(cmd + ' ')
    setShowCommands(false)
  }

  return (
    <div className="relative border-t border-[var(--color-border)] p-3">
      {showCommands && filteredCommands.length > 0 && (
        <div className="absolute bottom-full left-3 mb-1 w-48 rounded-lg border border-[var(--color-border)] bg-[var(--color-bg)] shadow-lg">
          {filteredCommands.map((c) => (
            <button
              key={c.cmd}
              onClick={() => selectCommand(c.cmd)}
              className="flex w-full items-center justify-between px-3 py-2 text-sm hover:bg-[var(--color-bg-tertiary)]"
            >
              <span className="font-mono text-[var(--color-text)]">{c.cmd}</span>
              <span className="text-xs text-[var(--color-text-muted)]">{c.desc}</span>
            </button>
          ))}
        </div>
      )}
      <form onSubmit={handleSubmit} className="flex items-center gap-2">
        <input
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="输入消息或 / 查看命令..."
          disabled={disabled}
          className="flex-1 rounded-md border border-[var(--color-border)] bg-[var(--color-bg)] px-3 py-2 text-sm outline-none focus:border-[var(--color-primary)] disabled:opacity-50"
        />
        <button
          type="submit"
          disabled={disabled || !value.trim()}
          className="rounded-md bg-[var(--color-primary)] p-2 text-white hover:bg-[var(--color-primary-hover)] disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </form>
    </div>
  )
}
