import React, { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import Header from './components/Header';
import SignalsTab from './components/SignalsTab';
import PortfolioTab from './components/PortfolioTab';
import OptionsTab from './components/OptionsTab';

const API = 'http://localhost:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('signals');
  const [signals, setSignals] = useState(null);
  const [profit, setProfit] = useState(null);
  const [lots, setLots] = useState(null);
  const [options, setOptions] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reloading, setReloading] = useState(false);
  const [backendOffline, setBackendOffline] = useState(false);
  const [tokenExpired, setTokenExpired] = useState(false);
  const [errorMsg, setErrorMsg] = useState(null);
  const [lastRefreshed, setLastRefreshed] = useState(null);

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      const [sigRes, profRes, lotsRes, optsRes] = await Promise.all([
        axios.get(`${API}/signals`),
        axios.get(`${API}/profit`),
        axios.get(`${API}/lots`),
        axios.get(`${API}/options`),
      ]);
      setSignals(sigRes.data);
      setProfit(profRes.data);
      setLots(lotsRes.data);
      setOptions(optsRes.data);
      setBackendOffline(false);
      setTokenExpired(false);
      setLastRefreshed(new Date());
    } catch (err) {
      if (!err.response) {
        setBackendOffline(true);
      } else if (err.response?.status === 503) {
        setTokenExpired(true);
      } else {
        setErrorMsg(err.response?.data?.detail || err.message);
      }
    } finally {
      setLoading(false);
    }
  }, []);

  const handleReload = async () => {
    setReloading(true);
    try {
      await axios.post(`${API}/reload`);
      await fetchAll();
    } catch {
      setErrorMsg('Reload failed — is the backend running?');
    } finally {
      setReloading(false);
    }
  };

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  const alertCount = signals?.signals?.filter(s => (s.effective_stage ?? s.signal_stage) >= 2).length ?? 0;

  return (
    <div className="app">
      <Header
        marketGate={signals?.market_gate}
        loading={loading}
        reloading={reloading}
        onReload={handleReload}
        lastRefreshed={lastRefreshed}
      />

      {backendOffline && (
        <div className="banner banner-error">
          <strong>Backend offline</strong> — run{' '}
          <code>uvicorn api.server:app --host 127.0.0.1 --port 8000 --reload</code>{' '}
          from the <code>backend/</code> folder.
        </div>
      )}
      {tokenExpired && (
        <div className="banner banner-warning">
          <strong>Schwab token expired</strong> — check the terminal for re-auth
          instructions, then run <code>python backend/auth/schwab_auth.py</code>.
        </div>
      )}
      {errorMsg && (
        <div className="banner banner-error">
          <strong>Error:</strong> {errorMsg}
        </div>
      )}

      <div className="tabs">
        {[
          { id: 'signals', label: 'Signals', count: alertCount },
          { id: 'portfolio', label: 'Portfolio' },
          { id: 'options', label: 'Options' },
        ].map(({ id, label, count }) => (
          <button
            key={id}
            className={`tab-btn ${activeTab === id ? 'active' : ''}`}
            onClick={() => setActiveTab(id)}
          >
            {label}
            {count > 0 && <span className="badge">{count}</span>}
          </button>
        ))}
      </div>

      <div className="tab-content">
        {activeTab === 'signals' && <SignalsTab data={signals} loading={loading} />}
        {activeTab === 'portfolio' && (
          <PortfolioTab profit={profit} lots={lots} loading={loading} />
        )}
        {activeTab === 'options' && <OptionsTab data={options} loading={loading} />}
      </div>
    </div>
  );
}
