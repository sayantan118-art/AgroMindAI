import { Component } from 'react'

export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }

  componentDidCatch(error) {
    console.error('Unexpected UI error:', error)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="card" style={{ padding: 24, textAlign: 'center' }}>
          <div style={{ color: '#fca5a5', fontWeight: 700, marginBottom: 8 }}>Something went wrong</div>
          <div style={{ color: '#94a3b8', marginBottom: 12 }}>The dashboard hit an unexpected error. Please refresh and try again.</div>
          <button
            onClick={() => window.location.reload()}
            style={{ background: '#2563eb', color: '#fff', border: 'none', borderRadius: 8, padding: '8px 12px', cursor: 'pointer' }}
          >
            Reload page
          </button>
        </div>
      )
    }

    return this.props.children
  }
}
