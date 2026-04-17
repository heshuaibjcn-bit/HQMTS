import DOMPurify from 'dompurify'

interface Props {
  role: 'user' | 'assistant' | 'system'
  content: string
}

export function MessageBubble({ role, content }: Props) {
  const isUser = role === 'user'

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[80%] rounded-lg px-3 py-2 text-sm ${
          isUser
            ? 'bg-[var(--color-primary)] text-white'
            : 'bg-[var(--color-bg-tertiary)] text-[var(--color-text)]'
        }`}
      >
        {isUser ? (
          <p className="whitespace-pre-wrap">{content}</p>
        ) : (
          <div
            className="prose prose-sm max-w-none"
            dangerouslySetInnerHTML={{
              __html: DOMPurify.sanitize(content, {
                ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'table', 'tr', 'td', 'th'],
                ALLOWED_ATTR: [],
              }),
            }}
          />
        )}
      </div>
    </div>
  )
}
