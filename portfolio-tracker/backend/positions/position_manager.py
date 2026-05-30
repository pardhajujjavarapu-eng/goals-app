"""
Single source of truth for current holdings.
Reads trades.csv, computes net positions, stores in portfolio.db.
No Schwab API calls.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Allow running directly from backend/ or portfolio-tracker/
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from datetime import datetime
from sqlalchemy import Column, String, Float, DateTime, text
from sqlalchemy.orm import Session

from db import engine, Base

TRADES_PATH = Path(__file__).parent.parent.parent / "data" / "trades.csv"


class Position(Base):
    __tablename__ = "positions"
    ticker = Column(String, primary_key=True)
    total_shares = Column(Float, nullable=False)
    average_cost_basis = Column(Float, nullable=False)
    accounts = Column(String, nullable=False)
    last_updated = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)


def _compute_positions(df: pd.DataFrame) -> list[dict]:
    stock_df = df[df["action"].isin(["BUY", "SELL"])].copy()
    stock_df = stock_df.sort_values("date").reset_index(drop=True)

    # Track individual lots for FIFO / specific-ID matching
    lots: dict[str, dict] = {}
    # ticker -> {shares, cost_total, accounts}
    positions: dict[str, dict] = {}

    for _, row in stock_df.iterrows():
        ticker = str(row["ticker"])
        action = str(row["action"])
        shares = float(row["shares"])
        cost = float(row["cost_basis"])
        lot_id = str(row["lot_id"])
        account = str(row["account"])

        if ticker not in positions:
            positions[ticker] = {"shares": 0.0, "cost_total": 0.0, "accounts": set()}

        if action == "BUY":
            lots[lot_id] = {
                "ticker": ticker,
                "shares": shares,
                "cost_basis": cost,
                "account": account,
                "date": row["date"],
                "open": True,
            }
            positions[ticker]["shares"] += shares
            positions[ticker]["cost_total"] += shares * cost
            positions[ticker]["accounts"].add(account)

        elif action == "SELL":
            remaining = shares

            # 1. Specific identification by lot_id
            if (
                lot_id in lots
                and lots[lot_id]["ticker"] == ticker
                and lots[lot_id]["open"]
            ):
                lot = lots[lot_id]
                reduce = min(remaining, lot["shares"])
                positions[ticker]["shares"] -= reduce
                positions[ticker]["cost_total"] -= reduce * lot["cost_basis"]
                lot["shares"] -= reduce
                if lot["shares"] <= 0.001:
                    lot["open"] = False
                remaining -= reduce

            # 2. FIFO fallback
            if remaining > 0:
                fifo = sorted(
                    [l for l in lots.values() if l["ticker"] == ticker and l["open"]],
                    key=lambda x: x["date"],
                )
                for lot in fifo:
                    if remaining <= 0:
                        break
                    reduce = min(remaining, lot["shares"])
                    positions[ticker]["shares"] -= reduce
                    positions[ticker]["cost_total"] -= reduce * lot["cost_basis"]
                    lot["shares"] -= reduce
                    if lot["shares"] <= 0.001:
                        lot["open"] = False
                    remaining -= reduce

    result = []
    for ticker, pos in positions.items():
        if pos["shares"] > 0.001:
            avg_cost = pos["cost_total"] / pos["shares"]
            result.append(
                {
                    "ticker": ticker,
                    "total_shares": round(pos["shares"], 6),
                    "average_cost_basis": round(avg_cost, 4),
                    "accounts": ",".join(sorted(pos["accounts"])),
                    "last_updated": datetime.now(),
                }
            )
    return result


def reload() -> list[dict]:
    df = pd.read_csv(TRADES_PATH, parse_dates=["date"])
    positions = _compute_positions(df)

    with Session(engine) as session:
        session.execute(text("DELETE FROM positions"))
        for pos in positions:
            session.merge(Position(**pos))
        session.commit()

    return positions


def load_positions() -> list[dict]:
    with Session(engine) as session:
        rows = session.query(Position).all()
        if not rows:
            return reload()
        return [
            {
                "ticker": r.ticker,
                "total_shares": r.total_shares,
                "average_cost_basis": r.average_cost_basis,
                "accounts": r.accounts,
                "last_updated": (
                    r.last_updated.isoformat() if r.last_updated else None
                ),
            }
            for r in rows
        ]


def get_tickers() -> list[str]:
    return [p["ticker"] for p in load_positions()]
