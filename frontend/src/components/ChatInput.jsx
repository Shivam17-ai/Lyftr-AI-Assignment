import React, { useRef, useEffect } from 'react'

export function ChatInput({
  input,
  setInput,
  onSend,
  loading,
  maxChars = 4000
}) {
  const textareaRef = useRef(null)

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = `${Math.min(textareaRef.current.scrollHeight, 180)}px`
    }
  }, [input])

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      if (input.trim() && !loading) {
        onSend()
      }
    }
  }

  const charCount = input.length
  const isNearLimit = charCount > maxChars * 0.85
  const isAtLimit = charCount >= maxChars

  return (
    <div className="input-panel">
      <div className="input-container">
        <div className="input-box-wrapper">
          <textarea
            ref={textareaRef}
            data-testid="chat-input"
            className="chat-textarea"
            placeholder="Type your message... (Enter to send, Shift+Enter for new line)"
            rows={1}
            value={input}
            maxLength={maxChars}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={loading}
          />
          <button
            data-testid="send-button"
            className="send-btn"
            onClick={onSend}
            disabled={loading || !input.trim()}
            title="Send Message"
          >
            {loading ? (
              <span style={{ fontSize: '0.8rem' }}>...</span>
            ) : (
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="22" y1="2" x2="11" y2="13"></line>
                <polygon points="22 2 15 22 11 13 2 9 22 2"></polygon>
              </svg>
            )}
          </button>
        </div>

        <div className="input-footer">
          <span>AI Gateway with automated key failover &amp; response cache</span>
          <span
            className={`char-counter ${isAtLimit ? 'at-limit' : isNearLimit ? 'near-limit' : ''}`}
          >
            {charCount} / {maxChars}
          </span>
        </div>
      </div>
    </div>
  )
}
