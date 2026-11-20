import React from 'react'

export function DevTools({
  simulateFailure,
  setSimulateFailure
}) {
  return (
    <div className="devtools-bar">
      <div className="devtools-left">
        <span>🛠 DevTools:</span>
        <label htmlFor="sim-select" style={{ display: 'flex', alignItems: 'center', gap: '0.35rem' }}>
          {simulateFailure && <span className="sim-active-indicator" title="Simulation active" />}
          Simulate failure header:
        </label>
        <select
          id="sim-select"
          className="devtools-select"
          value={simulateFailure}
          onChange={(e) => setSimulateFailure(e.target.value)}
        >
          <option value="">None (Normal operation)</option>
          <option value="key_1=429">key_1=429 (Failover to key_2)</option>
          <option value="key_1=500">key_1=500 (Failover to key_2 on 500)</option>
          <option value="key_1=429,key_2=500">key_1=429,key_2=500 (Exhaust all keys &rarr; 503)</option>
          <option value="*=429">*=429 (All keys rate-limited &rarr; 503)</option>
        </select>
      </div>
      <div>
        <span>{simulateFailure ? `Header: X-Simulate-Failure: ${simulateFailure}` : 'Simulation inactive'}</span>
      </div>
    </div>
  )
}
