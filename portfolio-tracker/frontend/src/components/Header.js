import React from 'react';

export default function Header({ marketGate, loading, reloading, onReload, lastRefreshed }) {
  const gate = marketGate?.gate_label ?? null;

  return (
    <div className="header">
      <div className="header-left">
        <h1>Portfolio Tracker</h1>
      </div>
      <div className="header-right">
        {lastRefreshed && (
          <span className="last-refresh">
            Updated {lastRefreshed.toLocaleTimeString()}
          </span>
        )}
        {gate && (
          <span className={`gate-badge ${gate}`}>
            {gate === 'bull' ? 'Bull Market' : 'Bear Market'}
          </span>
        )}
        <button
          className="btn-reload"
          onClick={onReload}
          disabled={reloading || loading}
          title="Reload trades.csv and refresh all data"
        >
          {reloading ? <span className="spinner" /> : '↻'} Reload
        </button>
      </div>
    </div>
  );
}
