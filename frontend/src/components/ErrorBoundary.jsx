import React from 'react'

export class ErrorBoundary extends React.Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error, errorInfo) {
    console.error('ErrorBoundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{
          padding: '2rem',
          maxWidth: '600px',
          margin: '2rem auto',
          background: 'rgba(239, 68, 68, 0.1)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '0.75rem',
          color: '#ef4444',
          fontFamily: 'sans-serif'
        }}>
          <h2>Something went wrong</h2>
          <p style={{ marginTop: '0.5rem', color: '#9ca3af' }}>
            {this.state.error?.message || 'An unexpected client error occurred.'}
          </p>
          <button
            onClick={() => window.location.reload()}
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              borderRadius: '0.375rem',
              background: '#4f46e5',
              color: 'white',
              border: 'none',
              cursor: 'pointer'
            }}
          >
            Reload Application
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
