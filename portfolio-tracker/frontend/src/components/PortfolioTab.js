import React, { useState } from 'react';
import WhatIfModal from './WhatIfModal';

function fmt$(n, showSign = false) {
  if (n == null) return '—';
  const abs = Math.abs(Number(n)).toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  const prefix = n < 0 ? '-$' : showSign && n > 0 ? '+$' : '$';
  return `${prefix}${abs}`;
}

function SummaryCard({ title, value, cls, tooltip }) {
  return (
    <div className={`card ${cls || ''}`}>
      <div
        className="card-title"
        data-tooltip={tooltip || undefined}
        style={{ display: 'inline-block' }}
      >
        {title}{tooltip ? ' ⓘ' : ''}
      </div>
      <div
        className="card-value"
        style={{
          color: value > 0 ? '#16a34a' : value < 0 ? '#dc2626' : undefined,
          fontSize: '1.25rem',
        }}
      >
        {fmt$(value)}
      </div>
    </div>
  );
}

export default function PortfolioTab({ profit, lots, loading }) {
  const [whatIfTicker, setWhatIfTicker] = useState(null);

  if (loading && !profit) return <p className="loading-text">Loading portfolio…</p>;
  if (!profit) return <p className="loading-text">No data yet.</p>;

  const openLots = lots?.lots ?? [];

  // Group open lots by ticker for the what-if modal
  const lotsByTicker = openLots.reduce((acc, l) => {
    if (!acc[l.ticker]) acc[l.ticker] = [];
    acc[l.ticker].push(l);
    return acc;
  }, {});

  const perTicker = profit.per_ticker ?? [];

  return (
    <>
      {/* Summary cards */}
      <div className="summary-cards">
        <SummaryCard
          title="Unrealized ST"
          value={profit.unrealized_st}
          cls="st-tint"
          tooltip="Taxed as ordinary income"
        />
        <SummaryCard
          title="Unrealized LT"
          value={profit.unrealized_lt}
          cls="lt-tint"
          tooltip="Taxed at 0 / 15 / 20% depending on bracket"
        />
        <SummaryCard title="Realized ST" value={profit.realized_st} cls="st-tint" />
        <SummaryCard title="Realized LT" value={profit.realized_lt} cls="lt-tint" />
        <SummaryCard
          title="Options Income"
          value={profit.options_income_total}
          cls="opt-tint"
          tooltip="Premium from covered calls and cash-secured puts — taxed as short term"
        />
      </div>

      {/* Open positions table */}
      <div className="section-title">Open Positions</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Account</th>
              <th>Shares</th>
              <th>Avg Cost</th>
              <th>Adj Basis</th>
              <th>Current Price</th>
              <th>Unrealized P&amp;L</th>
              <th>Term</th>
              <th>Days Held</th>
              <th>Days to LT</th>
              <th>Options Income</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {openLots.map(lot => {
              const isLt = lot.is_long_term;
              const approaching = lot.approaching_lt;
              const rowClass = isLt ? 'row-lt' : approaching ? 'row-approaching-lt' : '';
              const pnl = lot.unrealized_pnl ?? 0;
              const ticker_data = perTicker.find(t => t.ticker === lot.ticker);
              const adjBasis = ticker_data?.adjusted_cost_basis;
              const optIncome = ticker_data?.options_income;

              return (
                <tr key={lot.lot_id} className={rowClass}>
                  <td style={{ fontWeight: 700 }}>{lot.ticker}</td>
                  <td>{lot.account}</td>
                  <td>{lot.shares}</td>
                  <td>${lot.cost_basis?.toFixed(2)}</td>
                  <td>
                    {adjBasis != null ? (
                      <span title="Cost basis reduced by options premium collected">
                        ${adjBasis.toFixed(2)}
                      </span>
                    ) : '—'}
                  </td>
                  <td>
                    {lot.current_price ? `$${lot.current_price.toFixed(2)}` : '—'}
                  </td>
                  <td className={pnl >= 0 ? 'pos' : 'neg'}>
                    {fmt$(pnl, true)}
                  </td>
                  <td>
                    <span className={`term-badge ${isLt ? 'term-lt' : 'term-st'}`}>
                      {isLt ? 'LT' : 'ST'}
                    </span>
                  </td>
                  <td>{lot.days_held}d</td>
                  <td>
                    {isLt ? (
                      <span className="days-to-lt done">✓ LT</span>
                    ) : lot.days_to_long_term > 0 ? (
                      <span className={`days-to-lt ${approaching ? 'approaching' : ''}`}>
                        {lot.days_to_long_term}d
                      </span>
                    ) : '—'}
                  </td>
                  <td>
                    {optIncome ? (
                      <span className="pos">${optIncome.toFixed(2)}</span>
                    ) : '—'}
                  </td>
                  <td>
                    {lotsByTicker[lot.ticker]?.length > 0 && (
                      <button
                        className="btn-whatif"
                        onClick={() => setWhatIfTicker(lot.ticker)}
                      >
                        What-If
                      </button>
                    )}
                  </td>
                </tr>
              );
            })}
            {openLots.length === 0 && (
              <tr>
                <td colSpan={12} style={{ textAlign: 'center', color: '#9ca3af', padding: '2rem' }}>
                  No open lots.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {/* Closed positions */}
      <ClosedLotsTable perTicker={perTicker} />

      {/* What-If Modal */}
      {whatIfTicker && (
        <WhatIfModal
          ticker={whatIfTicker}
          openLots={lotsByTicker[whatIfTicker] ?? []}
          onClose={() => setWhatIfTicker(null)}
        />
      )}
    </>
  );
}

function ClosedLotsTable({ perTicker }) {
  const closed = perTicker
    .flatMap(t =>
      (t.open_lots ?? []).length === 0 && (t.realized_st !== 0 || t.realized_lt !== 0)
        ? [t]
        : []
    );

  // Flatten to show per-ticker realized rows (detailed closed lots come from /lots endpoint;
  // here we show the ticker-level summary from the profit endpoint)
  const rows = perTicker.filter(t => t.realized_st !== 0 || t.realized_lt !== 0);
  if (rows.length === 0) return null;

  return (
    <>
      <div className="section-title" style={{ marginTop: '2rem' }}>Realized Positions</div>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Ticker</th>
              <th>Realized ST</th>
              <th>Realized LT</th>
              <th>Total Realized</th>
            </tr>
          </thead>
          <tbody>
            {rows.map(t => {
              const total = (t.realized_st ?? 0) + (t.realized_lt ?? 0);
              return (
                <tr key={t.ticker}>
                  <td style={{ fontWeight: 700 }}>{t.ticker}</td>
                  <td className={t.realized_st >= 0 ? 'pos' : 'neg'}>{fmt$(t.realized_st, true)}</td>
                  <td className={t.realized_lt >= 0 ? 'pos' : 'neg'}>{fmt$(t.realized_lt, true)}</td>
                  <td className={total >= 0 ? 'pos' : 'neg'}>{fmt$(total, true)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
