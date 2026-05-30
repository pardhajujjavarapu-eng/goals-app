"""
Tax lot engine.  No Schwab API calls — pure local logic.
Handles open lots, closed lots, premium tracking, profit summary,
and what-if sell analysis.
"""
from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

import pandas as pd

TRADES_PATH = Path(__file__).parent.parent.parent / "data" / "trades.csv"


def _load_trades() -> pd.DataFrame:
    df = pd.read_csv(TRADES_PATH, parse_dates=["date"])
    return df


def _to_date(val) -> date:
    # Check datetime (and pandas Timestamp, which subclasses it) before date,
    # because datetime is a subclass of date and Timestamp.__sub__ is incompatible
    # with plain date objects.
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    return datetime.strptime(str(val)[:10], "%Y-%m-%d").date()


# ---------------------------------------------------------------------------
# Open lots
# ---------------------------------------------------------------------------

def get_open_lots() -> list[dict]:
    df = _load_trades()
    buy_rows = df[df["action"] == "BUY"].copy()
    sell_rows = df[df["action"] == "SELL"].sort_values("date").copy()

    lots: dict[str, dict] = {}
    for _, row in buy_rows.iterrows():
        lid = str(row["lot_id"])
        lots[lid] = {
            "lot_id": lid,
            "ticker": str(row["ticker"]),
            "shares": float(row["shares"]),
            "cost_basis": float(row["cost_basis"]),
            "account": str(row["account"]),
            "purchase_date": _to_date(row["date"]),
            "open": True,
        }

    for _, row in sell_rows.iterrows():
        ticker = str(row["ticker"])
        remaining = float(row["shares"])
        lid = str(row["lot_id"])

        if lid in lots and lots[lid]["ticker"] == ticker and lots[lid]["open"]:
            lot = lots[lid]
            reduce = min(remaining, lot["shares"])
            lot["shares"] -= reduce
            if lot["shares"] <= 0.001:
                lot["open"] = False
            remaining -= reduce

        if remaining > 0:
            fifo = sorted(
                [l for l in lots.values() if l["ticker"] == ticker and l["open"]],
                key=lambda x: x["purchase_date"],
            )
            for lot in fifo:
                if remaining <= 0:
                    break
                reduce = min(remaining, lot["shares"])
                lot["shares"] -= reduce
                if lot["shares"] <= 0.001:
                    lot["open"] = False
                remaining -= reduce

    today = date.today()
    result = []
    for lot in lots.values():
        if not lot["open"] or lot["shares"] <= 0.001:
            continue
        days_held = (today - lot["purchase_date"]).days
        is_lt = days_held > 365
        days_to_lt = max(0, 366 - days_held) if not is_lt else 0
        result.append(
            {
                "lot_id": lot["lot_id"],
                "ticker": lot["ticker"],
                "shares": round(lot["shares"], 6),
                "cost_basis": lot["cost_basis"],
                "account": lot["account"],
                "purchase_date": str(lot["purchase_date"]),
                "days_held": days_held,
                "is_long_term": is_lt,
                "days_to_long_term": days_to_lt,
                "approaching_lt": 1 <= days_to_lt <= 60,
            }
        )
    return result


# ---------------------------------------------------------------------------
# Closed lots
# ---------------------------------------------------------------------------

def get_closed_lots() -> list[dict]:
    df = _load_trades()
    buy_rows = df[df["action"] == "BUY"].copy()
    sell_rows = df[df["action"] == "SELL"].sort_values("date").copy()

    buy_lots: dict[str, dict] = {}
    for _, row in buy_rows.iterrows():
        lid = str(row["lot_id"])
        buy_lots[lid] = {
            "lot_id": lid,
            "ticker": str(row["ticker"]),
            "shares": float(row["shares"]),
            "cost_basis": float(row["cost_basis"]),
            "purchase_date": _to_date(row["date"]),
        }

    closed: list[dict] = []

    def _record_close(lot: dict, closed_shares: float, sell_price: float, sell_dt: date):
        days_held = (sell_dt - lot["purchase_date"]).days
        closed.append(
            {
                "lot_id": lot["lot_id"],
                "ticker": lot["ticker"],
                "shares_sold": round(closed_shares, 6),
                "cost_basis": lot["cost_basis"],
                "sell_price": sell_price,
                "realized_gain": round((sell_price - lot["cost_basis"]) * closed_shares, 2),
                "term": "long" if days_held > 365 else "short",
                "purchase_date": str(lot["purchase_date"]),
                "close_date": str(sell_dt),
                "days_held": days_held,
            }
        )

    for _, row in sell_rows.iterrows():
        ticker = str(row["ticker"])
        remaining = float(row["shares"])
        sell_price = float(row["cost_basis"]) if float(row["cost_basis"]) > 0 else 0.0
        sell_dt = _to_date(row["date"])
        lid = str(row["lot_id"])

        if (
            lid in buy_lots
            and buy_lots[lid]["ticker"] == ticker
            and buy_lots[lid]["shares"] > 0
        ):
            lot = buy_lots[lid]
            reduce = min(remaining, lot["shares"])
            _record_close(lot, reduce, sell_price, sell_dt)
            lot["shares"] -= reduce
            remaining -= reduce

        if remaining > 0:
            fifo = sorted(
                [l for l in buy_lots.values() if l["ticker"] == ticker and l["shares"] > 0],
                key=lambda x: x["purchase_date"],
            )
            for lot in fifo:
                if remaining <= 0:
                    break
                reduce = min(remaining, lot["shares"])
                _record_close(lot, reduce, sell_price, sell_dt)
                lot["shares"] -= reduce
                remaining -= reduce

    return closed


# ---------------------------------------------------------------------------
# Premium tracker
# ---------------------------------------------------------------------------

def get_premium_summary() -> list[dict]:
    df = _load_trades()
    opts = df[df["action"].isin(["COVERED_CALL", "CSP"])].copy()

    summary: dict[str, dict] = {}
    for _, row in opts.iterrows():
        ticker = str(row["ticker"])
        if ticker not in summary:
            summary[ticker] = {"ticker": ticker, "total_premium_collected": 0.0, "trades": []}
        summary[ticker]["total_premium_collected"] += float(row["premium"])
        summary[ticker]["trades"].append(
            {
                "date": str(_to_date(row["date"])),
                "action": str(row["action"]),
                "premium": float(row["premium"]),
                "account": str(row["account"]),
                "lot_id": str(row["lot_id"]),
            }
        )
    return list(summary.values())


# ---------------------------------------------------------------------------
# Profit summary
# ---------------------------------------------------------------------------

def get_profit_summary(current_prices: dict) -> dict:
    open_lots = get_open_lots()
    closed_lots = get_closed_lots()
    premium_map: dict[str, float] = {
        ps["ticker"]: ps["total_premium_collected"] for ps in get_premium_summary()
    }

    unrealized_st = 0.0
    unrealized_lt = 0.0
    per_ticker: dict[str, dict] = {}

    def _ensure(ticker: str):
        if ticker not in per_ticker:
            per_ticker[ticker] = {
                "ticker": ticker,
                "unrealized_st": 0.0,
                "unrealized_lt": 0.0,
                "realized_st": 0.0,
                "realized_lt": 0.0,
                "options_income": 0.0,
                "open_lots": [],
            }

    for lot in open_lots:
        ticker = lot["ticker"]
        _ensure(ticker)
        price = current_prices.get(ticker, 0.0)
        gain = (price - lot["cost_basis"]) * lot["shares"]
        per_ticker[ticker]["open_lots"].append(
            {**lot, "current_price": price, "unrealized_pnl": round(gain, 2)}
        )
        if lot["is_long_term"]:
            unrealized_lt += gain
            per_ticker[ticker]["unrealized_lt"] += gain
        else:
            unrealized_st += gain
            per_ticker[ticker]["unrealized_st"] += gain

    realized_st = 0.0
    realized_lt = 0.0
    for lot in closed_lots:
        ticker = lot["ticker"]
        _ensure(ticker)
        if lot["term"] == "long":
            realized_lt += lot["realized_gain"]
            per_ticker[ticker]["realized_lt"] += lot["realized_gain"]
        else:
            realized_st += lot["realized_gain"]
            per_ticker[ticker]["realized_st"] += lot["realized_gain"]

    options_income_total = 0.0
    for ticker, premium in premium_map.items():
        _ensure(ticker)
        per_ticker[ticker]["options_income"] = premium
        options_income_total += premium

    # Compute adjusted cost basis per ticker
    positions_by_ticker: dict[str, dict] = {}
    for lot in open_lots:
        t = lot["ticker"]
        if t not in positions_by_ticker:
            positions_by_ticker[t] = {"total_shares": 0.0, "avg_cost": 0.0}
        positions_by_ticker[t]["total_shares"] += lot["shares"]

    for ticker, pos in positions_by_ticker.items():
        _ensure(ticker)
        premium = premium_map.get(ticker, 0.0)
        shares = pos["total_shares"]
        lots_for_ticker = [l for l in open_lots if l["ticker"] == ticker]
        if lots_for_ticker and shares > 0:
            avg_cost = sum(l["cost_basis"] * l["shares"] for l in lots_for_ticker) / shares
            adj = max(0.0, avg_cost - (premium / shares if shares > 0 else 0))
            per_ticker[ticker]["adjusted_cost_basis"] = round(adj, 4)
            per_ticker[ticker]["average_cost_basis"] = round(avg_cost, 4)
            per_ticker[ticker]["total_shares"] = round(shares, 6)

    return {
        "unrealized_st": round(unrealized_st, 2),
        "unrealized_lt": round(unrealized_lt, 2),
        "realized_st": round(realized_st, 2),
        "realized_lt": round(realized_lt, 2),
        "options_income_total": round(options_income_total, 2),
        "per_ticker": list(per_ticker.values()),
    }


# ---------------------------------------------------------------------------
# What-if sell calculator
# ---------------------------------------------------------------------------

def what_if_sell(
    ticker: str,
    lot_id: str,
    current_price: float,
    st_tax_rate: float = 0.35,
    lt_tax_rate: float = 0.15,
) -> dict:
    open_lots = get_open_lots()
    lot = next(
        (l for l in open_lots if l["lot_id"] == lot_id and l["ticker"] == ticker),
        None,
    )
    if not lot:
        raise ValueError(f"Open lot '{lot_id}' for {ticker} not found.")

    gross_gain = (current_price - lot["cost_basis"]) * lot["shares"]

    if lot["is_long_term"]:
        tax_now = max(0.0, gross_gain * lt_tax_rate)
        after_now = gross_gain - tax_now
        return {
            "ticker": ticker,
            "lot_id": lot_id,
            "shares": lot["shares"],
            "cost_basis": lot["cost_basis"],
            "current_price": current_price,
            "gross_gain": round(gross_gain, 2),
            "is_long_term": True,
            "days_held": lot["days_held"],
            "days_to_lt_treatment": 0,
            "tax_if_sold_now": round(tax_now, 2),
            "tax_if_waited": round(tax_now, 2),
            "after_tax_gain_now": round(after_now, 2),
            "after_tax_gain_if_waited": round(after_now, 2),
            "additional_after_tax_from_waiting": 0.0,
            "recommendation": "Already long-term. No additional tax benefit from waiting.",
        }

    tax_now = max(0.0, gross_gain * st_tax_rate)
    tax_waited = max(0.0, gross_gain * lt_tax_rate)
    after_now = gross_gain - tax_now
    after_waited = gross_gain - tax_waited
    additional = after_waited - after_now
    days_to_lt = lot["days_to_long_term"]

    return {
        "ticker": ticker,
        "lot_id": lot_id,
        "shares": lot["shares"],
        "cost_basis": lot["cost_basis"],
        "current_price": current_price,
        "gross_gain": round(gross_gain, 2),
        "is_long_term": False,
        "days_held": lot["days_held"],
        "days_to_lt_treatment": days_to_lt,
        "tax_if_sold_now": round(tax_now, 2),
        "tax_if_waited": round(tax_waited, 2),
        "after_tax_gain_now": round(after_now, 2),
        "after_tax_gain_if_waited": round(after_waited, 2),
        "additional_after_tax_from_waiting": round(additional, 2),
        "recommendation": (
            f"Waiting {days_to_lt} more day{'s' if days_to_lt != 1 else ''} "
            f"saves you an estimated ${additional:,.2f} in taxes."
        ),
    }
