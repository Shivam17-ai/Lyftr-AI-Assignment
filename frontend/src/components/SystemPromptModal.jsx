import React from 'react'

export function SystemPromptModal({
  isOpen,
  onClose,
  systemPrompt,
  setSystemPrompt
}) {
  if (!isOpen) return null

  return (
    <div className="system-prompt-panel">
      <div className="system-prompt-content">
        <div className="system-prompt-header">
          <span>Custom System Prompt (Per-session)</span>
          <button
            onClick={onClose}
            style={{
              background: 'transparent',
              border: 'none',
              color: 'var(--text-muted)',
              cursor: 'pointer',
              fontSize: '1rem'
            }}
          >
            ✕
          </button>
        </div>
        <textarea
          data-testid="system-prompt-input"
          className="system-prompt-textarea"
          placeholder="e.g. You are a concise, helpful assistant specialized in software architecture."
          value={systemPrompt}
          onChange={(e) => setSystemPrompt(e.target.value)}
          maxLength={4000}
        />
      </div>
    </div>
  )
}
