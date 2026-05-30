import React from 'react';

function StageBadge({ stage, label }) {
  return (
    <span className={`stage-badge stage-${stage}`}>
      {label ?? ['Clear', 'Warning', 'Alert', 'Confirm'][stage] ?? stage}
    </span>
  );
}

function Check({ val }) {
  return val ? (
    <span style={{ color: '#dc2626', fontWeight: 700 }}>✓</span>
  ) : (
    <span style={{ color: '#d1d5db' }}>—</span>
  );
}

function fmt(n, decimals = 2) {
  if (n == null) return '—';
  return Number(n).toFixed(decimals);
}

export default function SignalsTab({ data, loading }) {
  if (loading && !data) return <p className="loading-text">Loading signals…</p>;
  if (!data) return <p className="loading-text">No data yet.</p>;

  const { market_gate: gate, signals = [] } = data;
  const monitored = signals.length;
  const activeAlerts = signals.filter(s => s.signal_stage >= 2).length;
  const effectiveAlerts = signals.filter(
    s => (s.effective_stage ?? s.signal_stage) !== s.signal_stage
  ).length;

  return (
    <>
      {/* Summary cards */}
      <div className="summary-cards">
        <div className="card">
          <div className="card-title">Market Gate</div>
          {gate ? (
            <>
              <div
                className="card-value"
                style={{ color: gate.gate_label === 'bull' ? '#15803d' : '#b91c1c', fontSize: '1.1rem' }}
              >
                {gate.gate_label === 'bull' ? 'Bull Market' : 'Bear Market'}
              </div>
              <div className="card-sub">
                SPY ${fmt(gate.spy_current_price)} · 200 EMA ${fmt(gate.spy_200ema_value)}
              </div>
            </>
          ) : (
            <div className="card-value" style={{ fontSize: '0.9rem', color: '#9ca3af' }}>Loading…</div>
          )}
        </div>

        <div className="card">
          <div className="card-title">Positions Monitored</div>
          <div className="card-value">{monitored}</div>
        </div>

        <div className="card" style={{ borderColor: activeAlerts > 0 ? '#fca5a5' : undefined }}>
          <div className="card-title">Active Alerts</div>
          <div className="card-value" style={{ color: activeAlerts > 0 ? '#dc2626' : undefined }}>
            {activeAlerts}
          </div>
          <div className="card-sub">Stage 2+</div>
        </div>

        <div className="card">
          <div className="card-title">Effective Alerts</div>
          <div
            className="card-value"
            style={{ color: effectiveAlerts > 0 ? '#ea580c' : undefined }}
          >
            {effectiveAlerts}
          </div>
          <div className="card-sub">Bear-market adjusted</div>
        </div>
      </div>

      {/* Gate note */}
      {gate?.gate_note && (
        <div
          style={{
            background: gate.gate_label === 'bull' ? '#f0fdf4' : '#fef2f2',
            border: `1px solid ${gate.gate_label === 'bull' ? '#bbf7d0' : '#fecaca'}`,
            borderRadius: 8,
            padding: '0.65rem 1rem',
            fontSize: '0.825rem',
            marginBottom: '1.25rem',
            color: gate.gate_label === 'bull' ? '#15803d' : '#991b1b',
          }}
        >
          {gate.gate_note}
        </div>
      )}

      {/* Signals table */}
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Price</th>
              <th>Signal</th>
              <th>Effective</th>
              <th>Beta</th>
              <th>Excess vs SPY</th>
              <th>Days Below 50 EMA</th>
              <th>MACD Trend</th>
              <th>Death Cross</th>
              <th>Ratio MACD Bear</th>
            </tr>
          </thead>
          <tbody>
            {signals.map(sig => {
              const eff = sig.effective_stage ?? sig.signal_stage;
              const adjusted = eff !== sig.signal_stage;
              const excessColor =
                sig.excess_move > 0
                  ? '#16a34a'
                  : sig.excess_move < 0
                  ? '#dc2626'
                  : undefined;
              return (
                <tr key={sig.ticker}>
                  <td style={{ fontWeight: 700 }}>{sig.ticker}</td>
                  <td>${fmt(sig.current_price)}</td>
                  <td>
                    <StageBadge stage={sig.signal_stage} label={sig.signal_label} />
                  </td>
                  <td>
                    {adjusted ? (
                      <span title="Bear market adjusted">
                        <StageBadge stage={eff} /> <span style={{ fontSize: '0.68rem', color: '#b91c1c' }}>bear adj.</span>
                      </span>
                    ) : (
                      <StageBadge stage={eff} label={sig.signal_label} />
                    )}
                  </td>
                  <td>{sig.beta != null ? fmt(sig.beta, 2) : '—'}</td>
                  <td>
                    <span style={{ color: excessColor, fontWeight: 600 }}>
                      {sig.excess_move != null
                        ? `${sig.excess_move >= 0 ? '+' : ''}${(sig.excess_move * 100).toFixed(2)}%`
                        : '—'}
                    </span>
                  </td>
                  <td>{sig.days_below_50ema ?? 0}</td>
                  <td style={{ textTransform: 'capitalize' }}>{sig.macd_histogram_trend ?? '—'}</td>
                  <td><Check val={sig.death_cross} /></td>
                  <td><Check val={sig.ratio_macd_bearish} /></td>
                </tr>
              );
            })}
            {signals.length === 0 && (
              <tr>
                <td colSpan={10} style={{ textAlign: 'center', color: '#9ca3af', padding: '2rem' }}>
                  No positions found. Add trades to data/trades.csv and reload.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
