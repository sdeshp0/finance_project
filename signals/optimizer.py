"""Single-ticker signal optimizer: a brute-force sensitivity sweep over the
backtest engine.

Every candidate (a single signal, or a pair/triple of signals that fire in the
same direction within a short window of each other) is backtested long-only,
short-only and both ways, under both exit rules, across a grid of holding
periods. The settings are chosen on the first part of the history ("train")
and then re-run, unchanged, on the rest ("test") so the table shows whether a
result held up on data it wasn't picked from.

This is a search over many variants of the same small history, so the best
train rows are biased upward by construction - the test columns, the minimum
trade count, and the plateau-based holding period are there to make that
visible, not to remove it.
"""
from itertools import combinations

import numpy as np
import pandas as pd

from signals.backtest import (
    SIGNAL_COLUMNS,
    BacktestParams,
    get_signal_events,
    simulate_trades,
    summarize_trades,
)

SINGLE_SIGNALS = list(SIGNAL_COLUMNS) + ["RSI mean-reversion", "Overall Bias"]
HOLD_GRID = (1, 2, 3, 5, 7, 10, 15, 20, 30, 40, 60)
DIRECTIONS = {"Long": "long", "Short": "short", "Both": "both"}
EXIT_RULES = {"Fixed hold": False, "Until opposite signal": True}
RANK_METRICS = {"Compounded return": "total_compounded_return", "Win rate": "win_rate"}


def combine_events(events: list[pd.Series], window: int) -> pd.Series:
    """+1 on a bar where at least one member fires bullish and every member has
    fired bullish within the last `window` bars (this bar included); -1 likewise
    for bearish. A single-member list returns that member unchanged."""
    if len(events) == 1:
        return events[0].astype(int)
    out = pd.Series(0, index=events[0].index)
    for sign in (1, -1):
        hits = [(e == sign) for e in events]
        recent = [h.astype(int).rolling(window, min_periods=1).max().astype(bool) for h in hits]
        fire = pd.concat(recent, axis=1).all(axis=1) & pd.concat(hits, axis=1).any(axis=1)
        out[fire & (out == 0)] = sign
        out[fire & (out == -sign)] = 0  # both directions on one bar -> ambiguous, skip it
    return out.astype(int)


def plateau_pick(values: list[float]) -> int:
    """Index of the best holding period, chosen in two steps: smooth each point
    with its neighbours (median of i-1, i, i+1) and find the best smoothed spot,
    so one lucky holding period surrounded by poor ones doesn't win; then take
    the best raw value within one step of that spot. NaNs (too few trades) never
    win; -1 if everything is NaN."""
    arr = np.array(values, dtype=float)
    smooth = np.array([np.nanmedian(arr[max(0, i - 1): i + 2]) if not np.isnan(arr[i]) else np.nan
                       for i in range(len(arr))])
    if np.all(np.isnan(smooth)):
        return -1
    c = int(np.nanargmax(smooth))
    lo = max(0, c - 1)
    return lo + int(np.nanargmax(arr[lo: c + 2]))


def _stats(df, events, params):
    return summarize_trades(simulate_trades(df, events, params), df)


def candidates(include_triples: bool = False) -> list[tuple[str, ...]]:
    out = [(s,) for s in SINGLE_SIGNALS] + list(combinations(SINGLE_SIGNALS, 2))
    if include_triples:
        out += list(combinations(SINGLE_SIGNALS, 3))
    return out


def optimize(df: pd.DataFrame, rsi_low: float, rsi_high: float, window: int = 3,
             train_frac: float = 0.7, min_trades: int = 8, rank_by: str = "Compounded return",
             include_triples: bool = False, stop_loss_pct: float = 0.0, cost_bps: float = 0.0,
             progress=None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Returns (results, curves).

    results: one row per candidate x direction x exit rule that reached
    `min_trades` on train at some holding period, with the plateau-picked
    holding period and its train/test stats, sorted best-first by `rank_by`
    on train.
    curves: train stats at every holding period for those rows (for the
    return-vs-holding-period chart), keyed by the same Signals/Direction/Exit.
    """
    metric = RANK_METRICS[rank_by]
    split = int(len(df) * train_frac)
    train, test = df.iloc[:split], df.iloc[split:]
    base = {s: get_signal_events(s, df, rsi_low, rsi_high) for s in SINGLE_SIGNALS}

    rows, curves = [], []
    cands = candidates(include_triples)
    for k, cand in enumerate(cands):
        if progress:
            progress(k / len(cands))
        # Events come from the full history (indicators fully warmed up) and are
        # then sliced, so test-period signals don't restart a warm-up.
        ev = combine_events([base[s] for s in cand], window)
        ev_train, ev_test = ev.iloc[:split], ev.iloc[split:]
        n_bull, n_bear = int((ev_train == 1).sum()), int((ev_train == -1).sum())
        label = " + ".join(cand)
        for dir_label, direction in DIRECTIONS.items():
            possible = {"long": n_bull, "short": n_bear, "both": n_bull + n_bear}[direction]
            if possible < min_trades:  # can't reach min_trades at any holding period
                continue
            for exit_label, use_signal_exit in EXIT_RULES.items():
                grid = []
                for hold in HOLD_GRID:
                    p = BacktestParams(direction=direction, use_signal_exit=use_signal_exit,
                                       hold_days=hold, stop_loss_pct=stop_loss_pct, cost_bps=cost_bps)
                    s = _stats(train, ev_train, p)
                    grid.append(s)
                    curves.append({"Signals": label, "Direction": dir_label, "Exit": exit_label,
                                   "Hold": hold, "Trades": s["n_trades"], "Win rate": s["win_rate"],
                                   "Compounded return": s["total_compounded_return"]})
                scores = [g[metric] if g["n_trades"] >= min_trades else np.nan for g in grid]
                i = plateau_pick(scores)
                if i < 0:
                    continue
                hold = HOLD_GRID[i]
                p = BacktestParams(direction=direction, use_signal_exit=use_signal_exit,
                                   hold_days=hold, stop_loss_pct=stop_loss_pct, cost_bps=cost_bps)
                t = _stats(test, ev_test, p)
                rows.append({
                    "Signals": label, "Legs": len(cand), "Direction": dir_label, "Exit": exit_label,
                    "Best hold": hold,
                    "Train trades": grid[i]["n_trades"], "Train win rate": grid[i]["win_rate"],
                    "Train return": grid[i]["total_compounded_return"],
                    "Test trades": t["n_trades"], "Test win rate": t["win_rate"],
                    "Test return": t["total_compounded_return"],
                })
    if progress:
        progress(1.0)

    cols = ["Signals", "Legs", "Direction", "Exit", "Best hold", "Train trades", "Train win rate",
            "Train return", "Test trades", "Test win rate", "Test return"]
    results = pd.DataFrame(rows, columns=cols)
    results.insert(5, "Holds up", np.select(
        [results["Test trades"] == 0, results["Test return"] > 0],
        ["– no test trades", "✓ yes"], default="✗ no"))
    sort_col = "Train return" if metric == "total_compounded_return" else "Train win rate"
    results = results.sort_values([sort_col, "Train trades"], ascending=False, ignore_index=True)

    curves = pd.DataFrame(curves)
    if not results.empty:
        keep = results[["Signals", "Direction", "Exit"]].drop_duplicates()
        curves = curves.merge(keep, on=["Signals", "Direction", "Exit"])
    return results, curves
