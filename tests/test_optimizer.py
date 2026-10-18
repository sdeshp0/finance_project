import numpy as np
import pandas as pd

from signals.indicators import compute_indicators
from signals.optimizer import (
    HOLD_GRID,
    candidates,
    combine_events,
    optimize,
    plateau_pick,
)


def _s(vals):
    return pd.Series(vals, index=pd.bdate_range("2025-01-01", periods=len(vals)))


def _ohlcv(close):
    close = pd.Series(close, index=pd.bdate_range("2024-01-01", periods=len(close)), dtype=float)
    return pd.DataFrame({"Open": close.shift(1).fillna(close.iloc[0]), "High": close + 1,
                         "Low": close - 1, "Close": close, "Volume": 1000.0})


# ---------------- combine_events ----------------

def test_single_member_is_unchanged():
    a = _s([0, 1, 0, -1])
    assert combine_events([a], 3).tolist() == [0, 1, 0, -1]


def test_pair_fires_on_the_later_leg_within_window():
    a = _s([1, 0, 0, 0, 0, 0])
    b = _s([0, 0, 1, 0, 0, 1])
    # b on bar 2 is within 3 bars of a on bar 0 -> fires; b on bar 5 is too late
    assert combine_events([a, b], 3).tolist() == [0, 0, 1, 0, 0, 0]


def test_pair_needs_the_same_direction():
    a = _s([1, 0, 0])
    b = _s([0, -1, 0])
    assert combine_events([a, b], 3).tolist() == [0, 0, 0]


def test_pair_bearish_and_same_bar():
    a = _s([0, -1, 0])
    b = _s([0, -1, 0])
    assert combine_events([a, b], 1).tolist() == [0, -1, 0]


def test_triple_needs_every_leg():
    a, b = _s([1, 0, 0, 0]), _s([0, 1, 0, 0])
    c_hit, c_miss = _s([0, 0, 1, 0]), _s([0, 0, 0, 0])
    assert combine_events([a, b, c_hit], 3).tolist() == [0, 0, 1, 0]
    assert combine_events([a, b, c_miss], 3).tolist() == [0, 0, 0, 0]


def test_conflicting_directions_on_one_bar_cancel():
    a = _s([1, -1, 0])
    b = _s([0, 1, 0])
    c = _s([0, -1, 0])
    # bar 1: a&b bullish within window AND a(-1) with c(-1) bearish -> pair a,b sees a=-1 on bar 1
    out = combine_events([_s([1, -1]), _s([1, -1])], 2)
    assert out.tolist() == [1, -1]
    assert combine_events([a, b, c], 2).iloc[1] == 0


# ---------------- plateau_pick ----------------

def test_plateau_beats_a_lone_spike():
    # index 1 is a spike between poor neighbours; 4 sits on a broad plateau
    assert plateau_pick([0.0, 0.9, 0.0, 0.5, 0.6, 0.5]) == 4


def test_plateau_ignores_nan_and_handles_all_nan():
    assert plateau_pick([np.nan, 0.1, np.nan]) == 1
    assert plateau_pick([np.nan, np.nan]) == -1
    assert plateau_pick([0.5, np.nan, 0.6]) == 2


# ---------------- optimize ----------------

def test_candidates_counts():
    singles = [c for c in candidates() if len(c) == 1]
    assert len(singles) == 12
    assert len(candidates()) == 12 + 66
    assert len(candidates(include_triples=True)) == 12 + 66 + 220


def _zigzag_df(n=400):
    t = np.arange(n)
    return compute_indicators(_ohlcv(100 + 10 * np.sin(t / 8) + t * 0.02))


def test_optimize_respects_min_trades_and_columns():
    df = _zigzag_df()
    res, curves = optimize(df, 30, 70, min_trades=5)
    assert not res.empty
    assert (res["Train trades"] >= 5).all()
    assert set(res["Direction"]) <= {"Long", "Short", "Both"}
    assert res["Best hold"].isin(HOLD_GRID).all()
    assert res["Holds up"].isin(["✓ yes", "✗ no", "– no test trades"]).all()
    # every result row has a full holding-period curve behind it
    for _, row in res.head(5).iterrows():
        c = curves[(curves.Signals == row.Signals) & (curves.Direction == row.Direction)
                   & (curves.Exit == row.Exit)]
        assert sorted(c["Hold"]) == sorted(HOLD_GRID)


def test_optimize_sorted_by_rank_metric():
    df = _zigzag_df()
    res, _ = optimize(df, 30, 70, min_trades=5, rank_by="Win rate")
    assert res["Train win rate"].is_monotonic_decreasing


def test_optimize_test_period_uses_only_later_bars():
    df = _zigzag_df()
    res_a, _ = optimize(df, 30, 70, min_trades=5, train_frac=0.7)
    # Changing only the test-period prices must not change any train column.
    df_b = df.copy()
    split = int(len(df) * 0.7)
    df_b.iloc[split:, df_b.columns.get_indexer(["Open", "High", "Low", "Close"])] *= 1.5
    res_b, _ = optimize(df_b, 30, 70, min_trades=5, train_frac=0.7)
    train_cols = ["Signals", "Direction", "Exit", "Best hold", "Train trades", "Train return"]
    pd.testing.assert_frame_equal(res_a[train_cols], res_b[train_cols])


def test_optimize_impossible_min_trades_gives_empty_frame():
    res, _ = optimize(_zigzag_df(), 30, 70, min_trades=1000)
    assert res.empty and "Holds up" in res.columns
