"""
Beta and excess-move calculations vs SPY.
Caches beta in portfolio.db; recalculates only if older than 7 days.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
from sqlalchemy import Column, String, Float, DateTime
from sqlalchemy.orm import Session

from db import engine, Base
from signals.ma_macd import fetch_ohlcv


class BetaCache(Base):
    __tablename__ = "beta_cache"
    ticker = Column(String, primary_key=True)
    beta = Column(Float, nullable=False)
    calculated_at = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)


def calculate_beta(client, ticker: str, lookback_days: int = 252) -> float:
    with Session(engine) as session:
        cached = session.query(BetaCache).filter(BetaCache.ticker == ticker).first()
        if cached and (datetime.now() - cached.calculated_at).days < 7:
            return float(cached.beta)

    stock_df = fetch_ohlcv(client, ticker, days=lookback_days + 30)
    spy_df = fetch_ohlcv(client, "SPY", days=lookback_days + 30)

    merged = (
        pd.merge(
            stock_df[["date", "close"]].rename(columns={"close": "stock"}),
            spy_df[["date", "close"]].rename(columns={"close": "spy"}),
            on="date",
            how="inner",
        )
        .tail(lookback_days)
    )

    if len(merged) < 30:
        return 1.0

    stock_ret = merged["stock"].pct_change().dropna().values
    spy_ret = merged["spy"].pct_change().dropna().values
    min_len = min(len(stock_ret), len(spy_ret))
    stock_ret = stock_ret[-min_len:]
    spy_ret = spy_ret[-min_len:]

    spy_var = float(np.var(spy_ret, ddof=1))
    if spy_var == 0:
        return 1.0
    cov = float(np.cov(stock_ret, spy_ret)[0][1])
    beta = cov / spy_var

    with Session(engine) as session:
        entry = session.query(BetaCache).filter(BetaCache.ticker == ticker).first()
        if entry:
            entry.beta = beta
            entry.calculated_at = datetime.now()
        else:
            session.add(BetaCache(ticker=ticker, beta=beta, calculated_at=datetime.now()))
        session.commit()

    return round(float(beta), 4)


def excess_move(client, ticker: str, beta: float, days: int = 5) -> float:
    stock_df = fetch_ohlcv(client, ticker, days=30).tail(days + 1)
    spy_df = fetch_ohlcv(client, "SPY", days=30).tail(days + 1)

    merged = pd.merge(
        stock_df[["date", "close"]].rename(columns={"close": "stock"}),
        spy_df[["date", "close"]].rename(columns={"close": "spy"}),
        on="date",
        how="inner",
    ).tail(days + 1)

    if len(merged) < 2:
        return 0.0

    stock_move = (merged["stock"].iloc[-1] / merged["stock"].iloc[0]) - 1
    spy_move = (merged["spy"].iloc[-1] / merged["spy"].iloc[0]) - 1
    return round(float(stock_move - beta * spy_move), 6)
