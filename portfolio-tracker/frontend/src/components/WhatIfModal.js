import React, { useState } from 'react';
import axios from 'axios';

const API = 'http://localhost:8000';

function fmt$(n) {
  if (n == null) return '—';
  return `$${Number(n).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export default function WhatIfModal({ ticker, openLots, onClose }) {
  const [lotId, setLotId] = useState(openLots[0]?.lot_id ?? '');
  const [stRate, setStRate] = useState(35);
  const [ltRate, setLtRate] = useState(15);
  const [result, setResult] = useState(null);
  const [calculating, setCalculating] = useState(false);
  const [error, setError] = useState(null);

  const handleCalculate = async () => {
    setCalculating(true);
    setError(null);
    try {
      const res = await axios.post(`${API}/what-if`, {
        ticker,
        lot_id: lotId,
        st_tax_rate: stRate / 100,
        lt_tax_rate: ltRate / 100,
      });
      setResult(res.data);
    } catch (err) {
      setError(err.response?.data?.detail ?? err.message);
    } finally {
      setCalculating(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={e => e.target === e.currentTarget && onClose()}>
      <div className="modal">
        <h2>What-If Sell — {ticker}</h2>

        <div className="modal-form">
          <div className="form-group">
            <label>Tax Lot</label>
            <select value={lotId} onChange={e => setLotId(e.target.value)}>
              {openLots.map(l => (
                <option key={l.lot_id} value={l.lot_id}>
                  {l.lot_id} — {l.shares} shares @ ${l.cost_basis} ({l.days_held}d held
                  {l.is_long_term ? ', LT' : `, ${l.days_to_long_term}d to LT`})
                </option>
              ))}
            </select>
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>ST Tax Rate (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={stRate}
                onChange={e => setStRate(Number(e.target.value))}
              />
            </div>
            <div className="form-group">
              <label>LT Tax Rate (%)</label>
              <input
                type="number"
                min={0}
                max={100}
                step={1}
                value={ltRate}
                onChange={e => setLtRate(Number(e.target.value))}
              />
            </div>
          </div>

          {error && (
            <div style={{ color: '#dc2626', fontSize: '0.8rem' }}>{error}</div>
          )}

          <div className="modal-actions">
            <button className="btn-secondary" onClick={onClose}>Cancel</button>
            <button
              className="btn-primary"
              onClick={handleCalculate}
              disabled={calculating || !lotId}
            >
              {calculating ? 'Calculating…' : 'Calculate'}
            </button>
          </div>
        </div>

        {result && (
          <div className="whatif-result">
            <hr style={{ border: 'none', borderTop: '1px solid #e5e7eb', margin: '0.5rem 0' }} />
            <div className="whatif-row">
              <span className="label">Shares</span>
              <span className="val">{result.shares}</span>
            </div>
            <div className="whatif-row">
              <span className="label">Cost Basis</span>
              <span className="val">{fmt$(result.cost_basis)}</span>
            </div>
            <div className="whatif-row">
              <span className="label">Current Price</span>
              <span className="val">{fmt$(result.current_price)}</span>
            </div>
            <div className="whatif-row">
              <span className="label">Gross Gain</span>
              <span className={`val ${result.gross_gain >= 0 ? 'pos' : 'neg'}`}>
                {fmt$(result.gross_gain)}
              </span>
            </div>
            <div className="whatif-row">
              <span className="label">Tax if Sold Today ({result.is_long_term ? 'LT' : 'ST'} rate)</span>
              <span className="val neg">{fmt$(result.tax_if_sold_now)}</span>
            </div>
            <div className="whatif-row">
              <span className="label">After-Tax Gain if Sold Today</span>
              <span className={`val ${result.after_tax_gain_now >= 0 ? 'pos' : 'neg'}`}>
                {fmt$(result.after_tax_gain_now)}
              </span>
            </div>
            {!result.is_long_term && (
              <>
                <div className="whatif-row">
                  <span className="label">Days to LT Treatment</span>
                  <span className="val" style={{ color: '#d97706' }}>
                    {result.days_to_lt_treatment} days
                  </span>
                </div>
                <div className="whatif-row">
                  <span className="label">Tax if Waited (LT rate)</span>
                  <span className="val">{fmt$(result.tax_if_waited)}</span>
                </div>
                <div className="whatif-row">
                  <span className="label">After-Tax Gain if Waited</span>
                  <span className={`val ${result.after_tax_gain_if_waited >= 0 ? 'pos' : 'neg'}`}>
                    {fmt$(result.after_tax_gain_if_waited)}
                  </span>
                </div>
                <div className="whatif-row">
                  <span className="label">Additional Gain from Waiting</span>
                  <span className="val pos">{fmt$(result.additional_after_tax_from_waiting)}</span>
                </div>
              </>
            )}
            <div className="recommendation">{result.recommendation}</div>
          </div>
        )}
      </div>
    </div>
  );
}
