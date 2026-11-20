import React from 'react'

function renderInline(text) {
  // Regex splitting by bold (**...**), inline code (`...`), italic (*...*)
  const regex = /(\*\*[^*]+\*\*|`[^`]+`|\*[^*]+\*)/g
  const parts = text.split(regex)

  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**') && part.length >= 4) {
      return <strong key={i} style={{ fontWeight: 600 }}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`') && part.length >= 2) {
      return (
        <code
          key={i}
          style={{
            background: 'var(--bg-tertiary)',
            padding: '0.1rem 0.35rem',
            borderRadius: '0.25rem',
            fontFamily: 'monospace',
            fontSize: '0.9em'
          }}
        >
          {part.slice(1, -1)}
        </code>
      )
    }
    if (part.startsWith('*') && part.endsWith('*') && part.length >= 2) {
      return <em key={i}>{part.slice(1, -1)}</em>
    }
    return part
  })
}

export function FormattedText({ content }) {
  if (!content) return null

  const lines = content.split('\n')
  const elements = []
  let inCodeBlock = false
  let codeBuffer = []
  let keyCounter = 0

  for (let idx = 0; idx < lines.length; idx++) {
    const line = lines[idx]

    // Handle code fences
    if (line.trim().startsWith('```')) {
      if (inCodeBlock) {
        elements.push(
          <pre
            key={keyCounter++}
            style={{
              background: 'var(--bg-tertiary)',
              padding: '0.75rem',
              borderRadius: '0.5rem',
              overflowX: 'auto',
              margin: '0.5rem 0',
              fontFamily: 'monospace',
              fontSize: '0.85rem'
            }}
          >
            <code>{codeBuffer.join('\n')}</code>
          </pre>
        )
        codeBuffer = []
        inCodeBlock = false
      } else {
        inCodeBlock = true
        codeBuffer = []
      }
      continue
    }

    if (inCodeBlock) {
      codeBuffer.push(line)
      continue
    }

    // Headings
    if (line.startsWith('### ')) {
      elements.push(
        <h4
          key={keyCounter++}
          style={{
            margin: '0.75rem 0 0.25rem',
            fontSize: '1.05rem',
            fontWeight: 600,
            color: 'var(--text-primary)'
          }}
        >
          {renderInline(line.slice(4))}
        </h4>
      )
      continue
    }
    if (line.startsWith('## ')) {
      elements.push(
        <h3
          key={keyCounter++}
          style={{
            margin: '0.85rem 0 0.35rem',
            fontSize: '1.15rem',
            fontWeight: 600,
            color: 'var(--text-primary)'
          }}
        >
          {renderInline(line.slice(3))}
        </h3>
      )
      continue
    }
    if (line.startsWith('# ')) {
      elements.push(
        <h2
          key={keyCounter++}
          style={{
            margin: '1rem 0 0.4rem',
            fontSize: '1.25rem',
            fontWeight: 700,
            color: 'var(--text-primary)'
          }}
        >
          {renderInline(line.slice(2))}
        </h2>
      )
      continue
    }

    // Bullet lists (- or *)
    const bulletMatch = line.match(/^(\s*)[-*]\s+(.*)$/)
    if (bulletMatch) {
      const indent = bulletMatch[1].length * 10
      elements.push(
        <div
          key={keyCounter++}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.5rem',
            marginLeft: `${indent + 8}px`,
            marginTop: '0.2rem',
            marginBottom: '0.2rem'
          }}
        >
          <span style={{ color: 'var(--text-muted)' }}>•</span>
          <span style={{ flex: 1 }}>{renderInline(bulletMatch[2])}</span>
        </div>
      )
      continue
    }

    // Numbered lists (1. 2. etc.)
    const numMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/)
    if (numMatch) {
      const indent = numMatch[1].length * 10
      elements.push(
        <div
          key={keyCounter++}
          style={{
            display: 'flex',
            alignItems: 'flex-start',
            gap: '0.4rem',
            marginLeft: `${indent + 8}px`,
            marginTop: '0.2rem',
            marginBottom: '0.2rem'
          }}
        >
          <span style={{ color: 'var(--text-muted)', minWidth: '1.2rem' }}>{numMatch[2]}.</span>
          <span style={{ flex: 1 }}>{renderInline(numMatch[3])}</span>
        </div>
      )
      continue
    }

    // Empty line
    if (!line.trim()) {
      elements.push(<div key={keyCounter++} style={{ height: '0.4rem' }} />)
      continue
    }

    // Normal paragraph
    elements.push(
      <p key={keyCounter++} style={{ margin: '0.25rem 0', lineHeight: 1.6 }}>
        {renderInline(line)}
      </p>
    )
  }

  return <div>{elements}</div>
}
