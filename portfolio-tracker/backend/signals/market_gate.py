"""
Market-wide regime filter using SPY 50/200-day EMA and MACD.
Returns gate_label = 'bull' | 'bear'.
In bear market, a stock at signal stage 2 should be treated as stage 3.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import pandas_ta as ta

from signals.ma_macd import fetch_ohlcv


def get_market_gate(client) -> dict:
    spy_df = fetch_ohlcv(client, "SPY", days=300)

    if len(spy_df) < 50:
        return {
            "spy_above_200ema": True,
            "spy_200ema_value": 0.0,
            "spy_current_price": 0.0,
            "spy_macd_bullish": True,
            "gate_label": "bull",
            "gate_note": "Insufficient SPY data to determine market regime.",
        }

    spy_df = spy_df.copy()
    spy_df["ema50"] = ta.ema(spy_df["close"], length=50)
    spy_df["ema200"] = ta.ema(spy_df["close"], length=200)

    macd_out = ta.macd(spy_df["close"], fast=12, slow=26, signal=9)
    spy_df["macd"] = macd_out["MACD_12_26_9"]
    spy_df["macd_sig"] = macd_out["MACDs_12_26_9"]

    valid = spy_df.dropna(subset=["ema50", "macd"])
    if valid.empty:
        return {
            "spy_above_200ema": True,
            "spy_200ema_value": 0.0,
            "spy_current_price": float(spy_df["close"].iloc[-1]),
            "spy_macd_bullish": True,
            "gate_label": "bull",
            "gate_note": "Not enough SPY history to compute 200-day EMA.",
        }

    latest = valid.iloc[-1]
    current_price = float(latest["close"])
    ema200 = float(latest["ema200"]) if not pd.isna(latest["ema200"]) else None
    macd_val = float(latest["macd"])
    macd_sig = float(latest["macd_sig"])

    above_200 = bool(ema200 is not None and current_price > ema200)
    macd_bullish = bool(macd_val > macd_sig)
    ema200_display = round(ema200, 2) if ema200 else 0.0

    if above_200 and macd_bullish:
        gate_label = "bull"
        note = (
            f"SPY is trading above its 200-day EMA (${ema200_display:,.2f}) "
            f"with bullish MACD momentum."
        )
    elif above_200 and not macd_bullish:
        gate_label = "bull"
        note = (
            f"SPY is above its 200-day EMA (${ema200_display:,.2f}) "
            f"but MACD momentum is weakening — watch for deterioration."
        )
    elif not above_200 and macd_bullish:
        gate_label = "bear"
        note = (
            f"SPY is below its 200-day EMA (${ema200_display:,.2f}) — "
            f"bear market regime despite short-term MACD bounce."
        )
    else:
        gate_label = "bear"
        note = (
            f"SPY is below its 200-day EMA (${ema200_display:,.2f}) "
            f"with bearish MACD — confirmed bear market conditions."
        )

    return {
        "spy_above_200ema": above_200,
        "spy_200ema_value": ema200_display,
        "spy_current_price": round(current_price, 2),
        "spy_macd_bullish": macd_bullish,
        "gate_label": gate_label,
        "gate_note": note,
    }
