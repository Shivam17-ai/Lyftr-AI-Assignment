import React from 'react'
import { FormattedText } from './FormattedText'

export function ChatMessage({ message }) {
  const isUser = message.role === 'user'
  const isError = message.isError

  if (isUser) {
    return (
      <div className="message-wrapper user">
        <div className="message-body">
          <div className="message-bubble">{message.content}</div>
        </div>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="message-wrapper error">
        <div className="avatar assistant">⚠</div>
        <div className="message-body">
          <div className="message-bubble">{message.content}</div>
        </div>
      </div>
    )
  }

  const meta = message.metadata || {}
  const isCache = meta.resolution_source === 'LLM_CACHE'

  return (
    <div className="message-wrapper assistant" data-testid="assistant-message">
      <div className="avatar assistant">AI</div>
      <div className="message-body">
        <div className="message-bubble">
          <FormattedText content={message.content} />
        </div>

        <div className="metadata-row">
          {/* Resolution source badge */}
          <span className={`meta-chip ${isCache ? 'badge-cache' : 'badge-live'}`}>
            {isCache ? '⚡ ' : '🌐 '}
            <span data-testid="meta-source">{meta.resolution_source}</span>
          </span>

          {/* Model name */}
          <span className="meta-chip chip-model">
            <span data-testid="meta-model">{meta.model}</span>
          </span>

          {/* Latency */}
          <span className="meta-chip chip-latency">
            <span data-testid="meta-latency">{meta.latency_ms} ms</span>
          </span>

          {/* Tokens */}
          <span className="meta-chip chip-tokens">
            <span className="meta-chip-label">in:</span>
            <span data-testid="meta-input-tokens">{meta.input_tokens}</span>
            <span className="meta-chip-label" style={{ marginLeft: '0.4rem' }}>out:</span>
            <span data-testid="meta-output-tokens">{meta.output_tokens}</span>
          </span>

          {/* Key ID & Fallback attempts if present */}
          {meta.key_id && (
            <span className="meta-chip meta-key-chip" title="Key ID & Fallback Attempts">
              {meta.key_id} • {meta.fallback_attempts} fallback{meta.fallback_attempts === 1 ? '' : 's'}
            </span>
          )}
        </div>
      </div>
    </div>
  )
}
