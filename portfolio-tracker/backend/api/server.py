"""
FastAPI backend for portfolio-tracker.
Binds to 127.0.0.1:8000 only.  CORS restricted to http://localhost:3000.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

# Make backend/ importable when uvicorn is run from backend/
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

load_dotenv(Path(__file__).parent.parent.parent / ".env")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_PATH = Path(__file__).parent.parent.parent / "logs" / "app.log"
LOG_PATH.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("portfolio_tracker")

# ---------------------------------------------------------------------------
# Lazy imports (after sys.path is set)
# ---------------------------------------------------------------------------
from auth.schwab_auth import get_client
from positions.position_manager import (
    load_positions,
    get_tickers,
    reload as reload_positions,
)
from positions.tax_lots import (
    get_open_lots,
    get_closed_lots,
    get_profit_summary,
    what_if_sell,
)
from signals.ma_macd import calculate_signals
from signals.beta_filter import calculate_beta, excess_move
from signals.market_gate import get_market_gate

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Portfolio Tracker", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_client = None
_account_last4 = "????"
TRADES_PATH = Path(__file__).parent.parent.parent / "data" / "trades.csv"


@app.on_event("startup")
async def startup():
    global _client, _account_last4
    try:
        _client = get_client()
        acct = os.getenv("SCHWAB_ACCOUNT_NUMBER", "")
        _account_last4 = acct[-4:] if len(acct) >= 4 else acct or "????"
        logger.info(f"Portfolio Tracker started. Account: ...{_account_last4}")
    except Exception as exc:
        logger.error(f"Startup — could not initialise Schwab client: {exc}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _require_client():
    if _client is None:
        raise HTTPException(
            status_code=503,
            detail="Schwab client not initialised. Run python backend/auth/schwab_auth.py first.",
        )
    return _client


def _fetch_prices(tickers: list[str]) -> dict[str, float]:
    if not tickers:
        return {}
    client = _require_client()
    try:
        resp = client.get_quotes(tickers)
        raw = resp.json()
        return {
            t: float(raw[t]["quote"].get("lastPrice", 0))
            for t in tickers
            if t in raw
        }
    except Exception as exc:
        logger.error(f"Price fetch failed: {exc}")
        return {}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "account_last4": _account_last4,
        "token_valid": _client is not None,
    }


@app.get("/positions")
async def positions():
    try:
        pos_list = load_positions()
        tickers = [p["ticker"] for p in pos_list]
        prices = _fetch_prices(tickers)
        for pos in pos_list:
            price = prices.get(pos["ticker"], 0.0)
            pos["current_price"] = price
            pos["unrealized_pnl"] = round(
                (price - pos["average_cost_basis"]) * pos["total_shares"], 2
            )
        return {"positions": pos_list}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"/positions: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/signals")
async def signals():
    try:
        client = _require_client()
        tickers = get_tickers()
        market_gate = get_market_gate(client)
        signal_list = calculate_signals(client, tickers)
        is_bear = market_gate["gate_label"] == "bear"

        enriched = []
        for sig in signal_list:
            beta = 1.0
            exc = 0.0
            try:
                beta = calculate_beta(client, sig["ticker"])
                exc = excess_move(client, sig["ticker"], beta)
            except Exception as e:
                logger.warning(f"beta/excess_move {sig['ticker']}: {e}")

            eff_stage = sig["signal_stage"]
            if is_bear and sig["signal_stage"] == 2:
                eff_stage = 3

            enriched.append({**sig, "beta": beta, "excess_move": exc, "effective_stage": eff_stage})

        enriched.sort(key=lambda x: x["effective_stage"], reverse=True)
        return {"market_gate": market_gate, "signals": enriched}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"/signals: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/profit")
async def profit():
    try:
        tickers = get_tickers()
        prices = _fetch_prices(tickers)
        return get_profit_summary(prices)
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"/profit: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/lots")
async def lots():
    try:
        open_lots = get_open_lots()
        tickers = list({lot["ticker"] for lot in open_lots})
        prices = _fetch_prices(tickers)
        for lot in open_lots:
            price = prices.get(lot["ticker"], 0.0)
            lot["current_price"] = price
            lot["unrealized_pnl"] = round((price - lot["cost_basis"]) * lot["shares"], 2)
        return {"lots": open_lots}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"/lots: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/options")
async def options():
    try:
        df = pd.read_csv(TRADES_PATH, parse_dates=["date"])
        opts = df[df["action"].isin(["COVERED_CALL", "CSP"])].copy()
        tickers = list(set(opts["ticker"].tolist()))
        prices = _fetch_prices(tickers)

        today = datetime.now().date()
        result = []
        for _, row in opts.iterrows():
            trade_date = row["date"].date() if hasattr(row["date"], "date") else row["date"]
            result.append(
                {
                    "ticker": str(row["ticker"]),
                    "type": "Covered Call" if row["action"] == "COVERED_CALL" else "Cash Secured Put",
                    "account": str(row["account"]),
                    "premium": float(row["premium"]),
                    "date_opened": str(trade_date),
                    "days_open": (today - trade_date).days,
                    "underlying_price": prices.get(str(row["ticker"]), 0.0),
                    "lot_id": str(row["lot_id"]),
                    "note": (
                        "Add strike and expiry columns to trades.csv "
                        "for full options tracking"
                    ),
                }
            )

        total_premium = round(sum(r["premium"] for r in result), 2)
        return {"total_premium": total_premium, "options": result}
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"/options: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


class WhatIfRequest(BaseModel):
    ticker: str
    lot_id: str
    st_tax_rate: float = 0.35
    lt_tax_rate: float = 0.15


@app.post("/what-if")
async def what_if(req: WhatIfRequest):
    try:
        prices = _fetch_prices([req.ticker])
        price = prices.get(req.ticker, 0.0)
        if price == 0.0:
            raise HTTPException(
                status_code=404, detail=f"Could not fetch current price for {req.ticker}"
            )
        return what_if_sell(req.ticker, req.lot_id, price, req.st_tax_rate, req.lt_tax_rate)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        logger.error(f"/what-if: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/reload")
async def reload():
    try:
        positions = reload_positions()
        return {"status": "reloaded", "positions_count": len(positions)}
    except Exception as exc:
        logger.error(f"/reload: {exc}")
        raise HTTPException(status_code=500, detail=str(exc))
