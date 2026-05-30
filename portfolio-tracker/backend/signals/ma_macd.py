"""
MA / MACD signal detection.
Fetches OHLCV from Schwab API, caches in portfolio.db, computes
50/200-day EMA, MACD, divergence, death cross, and ratio MACD vs SPY.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, date as date_type

import numpy as np
import pandas as pd
import pandas_ta as ta
from sqlalchemy import Column, String, Float, Integer, Date, DateTime, UniqueConstraint, text
from sqlalchemy.orm import Session

from db import engine, Base


class PriceCache(Base):
    __tablename__ = "price_cache"
    __table_args__ = (UniqueConstraint("ticker", "date", name="uq_price_ticker_date"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    ticker = Column(String, nullable=False, index=True)
    date = Column(Date, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    volume = Column(Float)
    fetched_at = Column(DateTime, nullable=False)


Base.metadata.create_all(engine)

# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------

def _get_cached(ticker: str, days: int) -> pd.DataFrame | None:
    cutoff = datetime.now() - timedelta(days=1)
    start = date_type.today() - timedelta(days=days + 60)
    with Session(engine) as session:
        rows = (
            session.query(PriceCache)
            .filter(
                PriceCache.ticker == ticker,
                PriceCache.date >= start,
                PriceCache.fetched_at >= cutoff,
            )
            .order_by(PriceCache.date)
            .all()
        )
    if len(rows) < max(30, int(days * 0.7)):
        return None
    return pd.DataFrame(
        [{"date": r.date, "open": r.open, "high": r.high, "low": r.low,
          "close": r.close, "volume": r.volume}
         for r in rows]
    )


def _store_cache(ticker: str, df: pd.DataFrame):
    now = datetime.now()
    cutoff = now - timedelta(days=1)
    with Session(engine) as session:
        session.execute(
            text("DELETE FROM price_cache WHERE ticker = :t AND fetched_at < :c"),
            {"t": ticker, "c": cutoff},
        )
        for _, row in df.iterrows():
            exists = (
                session.query(PriceCache)
                .filter(PriceCache.ticker == ticker, PriceCache.date == row["date"])
                .first()
            )
            if not exists:
                session.add(
                    PriceCache(
                        ticker=ticker,
                        date=row["date"],
                        open=row["open"],
                        high=row["high"],
                        low=row["low"],
                        close=row["close"],
                        volume=float(row["volume"]),
                        fetched_at=now,
                    )
                )
        session.commit()


# ---------------------------------------------------------------------------
# OHLCV fetch
# ---------------------------------------------------------------------------

def fetch_ohlcv(client, ticker: str, days: int = 300) -> pd.DataFrame:
    cached = _get_cached(ticker, days)
    if cached is not None:
        return cached

    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=days + 60)

    resp = client.get_price_history_every_day(ticker, start_datetime=start_dt, end_datetime=end_dt)
    data = resp.json()
    candles = data.get("candles", [])
    if not candles:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(candles)
    df["date"] = pd.to_datetime(df["datetime"], unit="ms").dt.date
    df = (
        df[["date", "open", "high", "low", "close", "volume"]]
        .sort_values("date")
        .reset_index(drop=True)
    )
    _store_cache(ticker, df)
    return df


# ---------------------------------------------------------------------------
# Signal calculation
# ---------------------------------------------------------------------------

STAGE_LABELS = {0: "Clear", 1: "Early Warning", 2: "Alert", 3: "Confirm"}


def calculate_signals(client, tickers: list[str]) -> list[dict]:
    spy_df = fetch_ohlcv(client, "SPY", days=300)
    results: list[dict] = []

    for ticker in tickers:
        try:
            df = fetch_ohlcv(client, ticker, days=300)
            if len(df) < 50:
                results.append(_error_row(ticker, "Not enough data"))
                continue

            df = df.copy()
            df["ema50"] = ta.ema(df["close"], length=50)
            df["ema200"] = ta.ema(df["close"], length=200)

            macd_df = ta.macd(df["close"], fast=12, slow=26, signal=9)
            df["macd"] = macd_df["MACD_12_26_9"]
            df["macd_sig"] = macd_df["MACDs_12_26_9"]
            df["macd_hist"] = macd_df["MACDh_12_26_9"]

            df = df.dropna(subset=["ema50", "macd", "macd_hist"]).reset_index(drop=True)
            if len(df) < 20:
                results.append(_error_row(ticker, "Not enough data after indicator calc"))
                continue

            last20 = df.tail(20)
            last10 = df.tail(10)
            last3 = df.tail(3).reset_index(drop=True)
            current = df.iloc[-1]

            current_price = float(current["close"])
            ema50_val = float(current["ema50"])
            ema200_val = float(current["ema200"]) if not pd.isna(current["ema200"]) else None

            # --- Bearish MACD divergence (price HH, MACD hist LH) over trailing 20 bars ---
            price_hh = float(current["high"]) >= float(last20["high"].iloc[:-1].max())
            macd_lh = float(current["macd_hist"]) < float(last20["macd_hist"].iloc[:-1].max())
            bearish_divergence = bool(price_hh and macd_lh)

            # --- MACD line crossed below signal within last 3 bars ---
            macd_cross_below = False
            for i in range(1, len(last3)):
                prev_above = last3["macd"].iloc[i - 1] >= last3["macd_sig"].iloc[i - 1]
                now_below = last3["macd"].iloc[i] < last3["macd_sig"].iloc[i]
                if prev_above and now_below:
                    macd_cross_below = True
                    break

            # --- Price below 50 EMA for 3+ consecutive bars ---
            days_below_50 = 0
            for i in range(len(df) - 1, -1, -1):
                if df["close"].iloc[i] < df["ema50"].iloc[i]:
                    days_below_50 += 1
                else:
                    break
            price_below_3days = days_below_50 >= 3

            # --- Death cross in last 10 bars ---
            death_cross = False
            if ema200_val is not None:
                last10_v = last10.dropna(subset=["ema200"]).reset_index(drop=True)
                for i in range(1, len(last10_v)):
                    was_above = last10_v["ema50"].iloc[i - 1] >= last10_v["ema200"].iloc[i - 1]
                    now_below_ema = last10_v["ema50"].iloc[i] < last10_v["ema200"].iloc[i]
                    if was_above and now_below_ema:
                        death_cross = True
                        break

            # --- Ratio MACD (stock / SPY) bearish crossover ---
            ratio_macd_bearish = False
            try:
                merged = pd.merge(
                    df[["date", "close"]].rename(columns={"close": "stock"}),
                    spy_df[["date", "close"]].rename(columns={"close": "spy"}),
                    on="date",
                    how="inner",
                )
                if len(merged) >= 50:
                    merged["ratio"] = merged["stock"] / merged["spy"]
                    rm = ta.macd(merged["ratio"], fast=12, slow=26, signal=9)
                    if rm is not None and not rm.empty:
                        col_m = [c for c in rm.columns if c.startswith("MACD_")][0]
                        col_s = [c for c in rm.columns if c.startswith("MACDs_")][0]
                        rm_tail = rm[[col_m, col_s]].dropna().tail(3).reset_index(drop=True)
                        for i in range(1, len(rm_tail)):
                            if (
                                rm_tail[col_m].iloc[i - 1] >= rm_tail[col_s].iloc[i - 1]
                                and rm_tail[col_m].iloc[i] < rm_tail[col_s].iloc[i]
                            ):
                                ratio_macd_bearish = True
                                break
            except Exception:
                pass

            # --- MACD histogram trend ---
            hist_tail = df["macd_hist"].tail(5).dropna()
            if len(hist_tail) >= 3:
                diffs = hist_tail.diff().dropna()
                neg = int((diffs < 0).sum())
                pos = int((diffs > 0).sum())
                hist_trend = "shrinking" if neg >= 3 else "growing" if pos >= 3 else "flat"
            else:
                hist_trend = "flat"

            # --- Stage assignment ---
            stage = 0
            if bearish_divergence:
                stage = max(stage, 1)
            if macd_cross_below or price_below_3days:
                stage = max(stage, 2)
            if death_cross or ratio_macd_bearish:
                stage = max(stage, 3)

            results.append(
                {
                    "ticker": ticker,
                    "current_price": current_price,
                    "signal_stage": stage,
                    "signal_label": STAGE_LABELS[stage],
                    "days_below_50ema": days_below_50,
                    "macd_histogram_trend": hist_trend,
                    "ratio_macd_bearish": ratio_macd_bearish,
                    "death_cross": death_cross,
                    "bearish_divergence": bearish_divergence,
                    "macd_cross_below": macd_cross_below,
                    "last_updated": datetime.now().isoformat(),
                }
            )

        except Exception as exc:
            results.append(_error_row(ticker, str(exc)))

    return results


def _error_row(ticker: str, msg: str) -> dict:
    return {
        "ticker": ticker,
        "error": msg,
        "signal_stage": 0,
        "signal_label": "Error",
        "days_below_50ema": 0,
        "macd_histogram_trend": "flat",
        "ratio_macd_bearish": False,
        "death_cross": False,
        "current_price": 0.0,
        "last_updated": datetime.now().isoformat(),
    }
