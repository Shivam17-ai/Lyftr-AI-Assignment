import React from 'react'

export function Header({
  healthInfo,
  onNewChat,
  onToggleSystemPrompt,
  systemPromptOpen,
  theme,
  onToggleTheme,
  user,
  onLogout,
  onToggleSidebar,
  sidebarOpen
}) {
  return (
    <header className="app-header">
      <div className="header-left">
        <button
          className="btn-icon sidebar-toggle-btn"
          onClick={onToggleSidebar}
          title="Toggle chat history sidebar"
        >
          {sidebarOpen ? '☰' : '☰'}
        </button>

        <div className="app-logo">⚡</div>
        <div className="app-title-group">
          <h1>LLM Chatbot</h1>
          <div className="app-subtitle">
            {healthInfo ? (
              <span>
                ● Online &bull; {healthInfo.keys_configured} keys &bull;{' '}
                {healthInfo.cache_enabled ? 'cache on' : 'cache off'}
              </span>
            ) : (
              <span>Connecting to gateway...</span>
            )}
          </div>
        </div>
      </div>

      <div className="header-right">
        <button
          className={`btn-icon ${systemPromptOpen ? 'btn-primary' : ''}`}
          onClick={onToggleSystemPrompt}
          title="Configure System Prompt"
        >
          ⚙ System Prompt
        </button>

        <button
          className="btn-icon"
          onClick={onNewChat}
          title="Start fresh conversation"
        >
          + New chat
        </button>

        <button
          className="btn-icon"
          onClick={onToggleTheme}
          title="Toggle Light/Dark Theme"
        >
          {theme === 'dark' ? '☀ Light' : '🌙 Dark'}
        </button>

        {user && (
          <div className="user-profile-badge">
            <span className="user-avatar-small">👤</span>
            <span className="user-email-text" title={user}>{user.split('@')[0]}</span>
            <button
              className="logout-mini-btn"
              onClick={onLogout}
              title="Sign out of demo"
            >
              Logout
            </button>
          </div>
        )}
      </div>
    </header>
  )
}
