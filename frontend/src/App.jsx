import React, { useState, useEffect, useRef } from 'react'
import { Header } from './components/Header'
import { ChatMessage } from './components/ChatMessage'
import { ChatInput } from './components/ChatInput'
import { DevTools } from './components/DevTools'
import { SystemPromptModal } from './components/SystemPromptModal'
import { Sidebar } from './components/Sidebar'
import { LoginScreen } from './components/LoginScreen'
import { ErrorBoundary } from './components/ErrorBoundary'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000'

function generateSessionId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return 's-' + crypto.randomUUID().slice(0, 8)
  }
  return 's-' + Math.random().toString(36).substring(2, 10)
}

const EXAMPLE_PROMPTS = [
  'What is the capital of France?',
  'Explain how LLM key failover works in 2 sentences.',
  'Write a Python function to check for prime numbers.',
  'What are the advantages of in-memory caching for LLMs?'
]

function App() {
  // Demo Login State
  const [user, setUser] = useState(() => {
    return sessionStorage.getItem('demo_user') || null
  })

  // Session ID regenerated on EVERY page load / new chat
  const [sessionId, setSessionId] = useState(generateSessionId)
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [systemPrompt, setSystemPrompt] = useState('')
  const [systemPromptOpen, setSystemPromptOpen] = useState(false)
  const [simulateFailure, setSimulateFailure] = useState('')
  const [healthInfo, setHealthInfo] = useState(null)
  const [theme, setTheme] = useState('dark')

  // Previous Chats Sidebar State
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [previousSessions, setPreviousSessions] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('saved_sessions') || '[]')
    } catch {
      return []
    }
  })

  const messagesEndRef = useRef(null)

  // Apply theme to document
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
  }, [theme])

  // Fetch health and backend sessions on load
  useEffect(() => {
    fetch(`${API_BASE}/health`)
      .then((res) => {
        if (!res.ok) throw new Error('Health check failed')
        return res.json()
      })
      .then((data) => setHealthInfo(data))
      .catch((err) => {
        console.warn('Backend health check error:', err)
        setHealthInfo({ status: 'offline', keys_configured: 0, cache_enabled: false })
      })

    // Load persisted sessions from backend
    fetch(`${API_BASE}/sessions`)
      .then((res) => res.ok ? res.json() : [])
      .then((backendSessions) => {
        if (backendSessions && Array.isArray(backendSessions) && backendSessions.length > 0) {
          setPreviousSessions((prev) => {
            const combinedMap = new Map()
            backendSessions.forEach((s) => combinedMap.set(s.session_id, s))
            prev.forEach((s) => {
              if (!combinedMap.has(s.session_id)) combinedMap.set(s.session_id, s)
            })
            const combined = Array.from(combinedMap.values())
            localStorage.setItem('saved_sessions', JSON.stringify(combined))
            return combined
          })
        }
      })
      .catch(() => {})
  }, [])

  // Auto-scroll when messages update
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  const handleLogin = (userEmail) => {
    setUser(userEmail)
    sessionStorage.setItem('demo_user', userEmail)
  }

  const handleLogout = () => {
    setUser(null)
    sessionStorage.removeItem('demo_user')
  }

  const handleToggleTheme = () => {
    setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))
  }

  const handleNewChat = () => {
    setSessionId(generateSessionId())
    setMessages([])
    setInput('')
  }

  // Load a previous chat from backend / history
  const handleSelectSession = async (selectedId) => {
    if (selectedId === sessionId && messages.length > 0) return
    setSessionId(selectedId)
    setLoading(true)
    try {
      const res = await fetch(`${API_BASE}/sessions/${selectedId}/messages`)
      if (res.ok) {
        const data = await res.json()
        setMessages(data.messages || [])
      } else {
        setMessages([])
      }
    } catch (err) {
      console.error('Failed to load session history:', err)
      setMessages([])
    } finally {
      setLoading(false)
    }
  }

  const handleSendMessage = async (textToSend) => {
    const text = (textToSend || input).trim()
    if (!text || loading) return

    // 1. Optimistically append user message
    const userMsg = { role: 'user', content: text }
    setMessages((prev) => [...prev, userMsg])
    setInput('')
    setLoading(true)

    // Track session in sidebar
    setPreviousSessions((prev) => {
      const exists = prev.find((s) => s.session_id === sessionId)
      let updated
      if (exists) {
        updated = prev
      } else {
        const title = text.length > 36 ? text.slice(0, 36) + '...' : text
        updated = [{ session_id: sessionId, title, last_active: new Date().toISOString() }, ...prev]
      }
      localStorage.setItem('saved_sessions', JSON.stringify(updated))
      return updated
    })

    try {
      const headers = {
        'Content-Type': 'application/json'
      }
      if (simulateFailure) {
        headers['X-Simulate-Failure'] = simulateFailure
      }

      const body = {
        session_id: sessionId,
        message: text
      }
      if (systemPrompt.trim()) {
        body.system_prompt = systemPrompt.trim()
      }

      const response = await fetch(`${API_BASE}/chat`, {
        method: 'POST',
        headers,
        body: JSON.stringify(body)
      })

      const data = await response.json()

      if (!response.ok) {
        let errorText = 'An error occurred during inference.'
        if (response.status === 503) {
          errorText = 'All providers are currently unavailable. Please try again in a moment.'
        } else if (response.status === 422) {
          errorText = typeof data.detail === 'string'
            ? data.detail
            : 'Validation error: please check message length and format.'
        } else if (data.detail) {
          errorText = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail)
        }
        setMessages((prev) => [
          ...prev,
          { role: 'assistant', content: errorText, isError: true }
        ])
      } else {
        setMessages((prev) => [
          ...prev,
          {
            role: 'assistant',
            content: data.reply,
            metadata: data.metadata
          }
        ])
      }
    } catch (err) {
      console.error('Fetch error:', err)
      setMessages((prev) => [
        ...prev,
        {
          role: 'assistant',
          content: 'Network error: could not connect to backend server. Make sure the backend is running.',
          isError: true
        }
      ])
    } finally {
      setLoading(false)
    }
  }

  // If not logged in, show Demo Login Screen
  if (!user) {
    return (
      <ErrorBoundary>
        <LoginScreen onLogin={handleLogin} />
      </ErrorBoundary>
    )
  }

  return (
    <ErrorBoundary>
      <div className="app-container">
        <Header
          healthInfo={healthInfo}
          onNewChat={handleNewChat}
          onToggleSystemPrompt={() => setSystemPromptOpen((prev) => !prev)}
          systemPromptOpen={systemPromptOpen}
          theme={theme}
          onToggleTheme={handleToggleTheme}
          user={user}
          onLogout={handleLogout}
          onToggleSidebar={() => setSidebarOpen((prev) => !prev)}
          sidebarOpen={sidebarOpen}
        />

        <SystemPromptModal
          isOpen={systemPromptOpen}
          onClose={() => setSystemPromptOpen(false)}
          systemPrompt={systemPrompt}
          setSystemPrompt={setSystemPrompt}
        />

        <div className="app-body-layout">
          <Sidebar
            isOpen={sidebarOpen}
            onToggle={() => setSidebarOpen((prev) => !prev)}
            sessions={previousSessions}
            currentSessionId={sessionId}
            onSelectSession={handleSelectSession}
            onNewChat={handleNewChat}
          />

          <main className="chat-main">
            <div className="messages-viewport">
              <div className="messages-container">
                {messages.length === 0 ? (
                  <div className="empty-state">
                    <div className="empty-icon">⚡</div>
                    <h2 className="empty-title">LLM Chatbot Gateway</h2>
                    <p className="empty-description">
                      Multi-key automated failover, intelligent caching, and per-turn metadata tracking.
                    </p>
                    <div className="prompt-suggestions">
                      {EXAMPLE_PROMPTS.map((prompt, idx) => (
                        <button
                          key={idx}
                          className="prompt-card"
                          onClick={() => handleSendMessage(prompt)}
                        >
                          {prompt}
                        </button>
                      ))}
                    </div>
                  </div>
                ) : (
                  messages.map((msg, index) => (
                    <ChatMessage key={index} message={msg} />
                  ))
                )}

                {loading && (
                  <div className="message-wrapper assistant">
                    <div className="avatar assistant">AI</div>
                    <div className="message-body">
                      <div className="typing-indicator">
                        <span>Thinking</span>
                        <div className="typing-dots">
                          <div className="typing-dot"></div>
                          <div className="typing-dot"></div>
                          <div className="typing-dot"></div>
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>
            </div>

            <ChatInput
              input={input}
              setInput={setInput}
              onSend={() => handleSendMessage()}
              loading={loading}
            />

            <DevTools
              simulateFailure={simulateFailure}
              setSimulateFailure={setSimulateFailure}
            />
          </main>
        </div>
      </div>
    </ErrorBoundary>
  )
}

export default App
