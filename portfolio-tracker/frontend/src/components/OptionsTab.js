import React from 'react';

function fmt$(n) {
  if (n == null) return '—';
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function OptionsTab({ data, loading }) {
  if (loading && !data) return <p className="loading-text">Loading options…</p>;
  if (!data) return <p className="loading-text">No data yet.</p>;

  const { total_premium = 0, options = [] } = data;

  return (
    <>
      <div className="options-note">
        <strong>Note:</strong> To enable full options tracking (strike, expiry, delta, DTE),
        add <code>strike</code>, <code>expiry</code>, and <code>contracts</code> columns to{' '}
        <code>data/trades.csv</code>.
      </div>

      {/* Total premium card */}
      <div className="summary-cards" style={{ marginBottom: '1.5rem' }}>
        <div className="card opt-tint">
          <div className="card-title">Total Premium Collected</div>
          <div className="card-value pos">{fmt$(total_premium)}</div>
          <div className="card-sub">All covered calls &amp; CSPs</div>
        </div>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Type</th>
              <th>Account</th>
              <th>Premium</th>
              <th>Date Opened</th>
              <th>Days Open</th>
              <th>Underlying Price</th>
              <th>Lot ID</th>
            </tr>
          </thead>
          <tbody>
            {options.map((opt, i) => (
              <tr key={`${opt.lot_id}-${i}`}>
                <td style={{ fontWeight: 700 }}>{opt.ticker}</td>
                <td>
                  <span
                    style={{
                      padding: '0.15rem 0.5rem',
                      borderRadius: 6,
                      fontSize: '0.72rem',
                      fontWeight: 700,
                      background: opt.type === 'Covered Call' ? '#eff6ff' : '#f0fdf4',
                      color: opt.type === 'Covered Call' ? '#2563eb' : '#15803d',
                    }}
                  >
                    {opt.type}
                  </span>
                </td>
                <td>{opt.account}</td>
                <td className="pos">{fmt$(opt.premium)}</td>
                <td>{opt.date_opened}</td>
                <td>{opt.days_open}d</td>
                <td>
                  {opt.underlying_price > 0 ? `$${opt.underlying_price.toFixed(2)}` : '—'}
                </td>
                <td style={{ color: '#6b7280', fontSize: '0.8rem' }}>{opt.lot_id}</td>
              </tr>
            ))}
            {options.length === 0 && (
              <tr>
                <td colSpan={8} style={{ textAlign: 'center', color: '#9ca3af', padding: '2rem' }}>
                  No covered calls or CSPs found in trades.csv.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    </>
  );
}
