import React from 'react'

export function Sidebar({
  isOpen,
  onToggle,
  sessions,
  currentSessionId,
  onSelectSession,
  onNewChat
}) {
  return (
    <aside className={`chat-sidebar ${isOpen ? 'open' : 'closed'}`}>
      <div className="sidebar-header">
        <button className="sidebar-new-btn" onClick={onNewChat} title="Start new chat session">
          <span>+ New Chat</span>
        </button>
        <button
          className="sidebar-close-btn"
          onClick={onToggle}
          title="Toggle sidebar"
        >
          {isOpen ? '◀' : '▶'}
        </button>
      </div>

      {isOpen && (
        <div className="sidebar-content">
          <div className="sidebar-label">Previous Chats</div>
          <div className="sidebar-sessions-list">
            {sessions.length === 0 ? (
              <div className="sidebar-empty">No previous chats saved yet</div>
            ) : (
              sessions.map((sess) => {
                const isActive = sess.session_id === currentSessionId
                return (
                  <button
                    key={sess.session_id}
                    className={`sidebar-session-item ${isActive ? 'active' : ''}`}
                    onClick={() => onSelectSession(sess.session_id)}
                    title={sess.title || sess.session_id}
                  >
                    <span className="session-icon">💬</span>
                    <span className="session-title">{sess.title || sess.session_id}</span>
                  </button>
                )
              })
            )}
          </div>
        </div>
      )}
    </aside>
  )
}
