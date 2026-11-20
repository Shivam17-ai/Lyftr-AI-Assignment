import React, { useState } from 'react'

export function LoginScreen({ onLogin }) {
  const [email, setEmail] = useState('demo@llmgateway.ai')
  const [password, setPassword] = useState('••••••••')

  const handleSubmit = (e) => {
    e.preventDefault()
    onLogin(email || 'demo@llmgateway.ai')
  }

  return (
    <div className="login-wrapper">
      <div className="login-card">
        <div className="login-header">
          <div className="login-logo">⚡</div>
          <h1 className="login-title">LLM Chatbot Gateway</h1>
          <p className="login-subtitle">Multi-key automated failover &amp; response caching</p>
        </div>

        <form onSubmit={handleSubmit} className="login-form">
          <div className="login-input-group">
            <label className="login-label">Email Address</label>
            <input
              type="email"
              className="login-input"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="developer@domain.com"
              required
            />
          </div>

          <div className="login-input-group">
            <label className="login-label">Password</label>
            <input
              type="password"
              className="login-input"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••"
              required
            />
          </div>

          <button type="submit" className="login-btn">
            Sign In to Gateway &rarr;
          </button>
        </form>

        <div className="login-footer">
          <div className="demo-badge">
            <span className="demo-dot" />
            <span>Demo Session &bull; Instant Access</span>
          </div>
          <button
            type="button"
            className="guest-login-btn"
            onClick={() => onLogin('guest@demo.com')}
          >
            Continue as Guest
          </button>
        </div>
      </div>
    </div>
  )
}
