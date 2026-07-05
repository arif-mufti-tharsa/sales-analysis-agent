"""
Analysis tools for the sales agent.

DESIGN RULE (docs/design.md #3): every tool returns a structured dict
    {"status": "ok" | "empty" | "error", "data": ..., "message": ...}
Never raise raw exceptions to the agent loop, never return silent empties.
The LLM is the consumer -- error messages must say HOW to fix the call.
"""

from pathlib import Path

import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "sales_data.csv"
DATA_RANGE = ("2026-04-01", "2026-06-30")

_df = None


def _load() -> pd.DataFrame:
    global _df
    if _df is None:
        _df = pd.read_csv(DATA_PATH, parse_dates=["date"])
    return _df


# ---------- structured result helpers ----------

def _ok(data) -> dict:
    return {"status": "ok", "data": data, "message": ""}


def _empty(message: str) -> dict:
    return {"status": "empty", "data": None, "message": message}


def _error(message: str) -> dict:
    return {"status": "error", "data": None, "message": message}


def _range_hint() -> str:
    return f"Dataset mencakup {DATA_RANGE[0]} s/d {DATA_RANGE[1]}."


# ---------- validation ----------

def _validate_dates(start_date: str, end_date: str):
    """Returns (start_ts, end_ts, None) if valid, else (None, None, error_dict)."""
    try:
        start = pd.to_datetime(start_date)
        end = pd.to_datetime(end_date)
    except (ValueError, TypeError):
        return None, None, _error(
            f"Format tanggal tidak valid: '{start_date}' / '{end_date}'. "
            f"Gunakan format YYYY-MM-DD. {_range_hint()}"
        )
    if start > end:
        return None, None, _error(
            f"start_date ({start_date}) lebih besar dari end_date ({end_date}). Tukar urutannya."
        )
    lo, hi = pd.to_datetime(DATA_RANGE[0]), pd.to_datetime(DATA_RANGE[1])
    if end < lo or start > hi:
        return None, None, _error(
            f"Periode {start_date} s/d {end_date} sepenuhnya di luar cakupan data. {_range_hint()}"
        )
    return start, end, None


def _suggest_products(name: str, limit: int = 3) -> list[str]:
    """Cheap 'did you mean' -- substring & token overlap match."""
    df = _load()
    candidates = sorted(set(df["product_name"]))
    name_l = name.lower()
    scored = []
    for c in candidates:
        c_l = c.lower()
        score = 0
        if name_l in c_l or c_l in name_l:
            score += 2
        score += len(set(name_l.split()) & set(c_l.split()))
        if score > 0:
            scored.append((score, c))
    scored.sort(reverse=True)
    return [c for _, c in scored[:limit]] or candidates[:limit]


# ---------- the 3 tools ----------

def get_sales_by_period(start_date: str, end_date: str) -> dict:
    """Total sales in a date range, with per-category breakdown."""
    start, end, err = _validate_dates(start_date, end_date)
    if err:
        return err

    df = _load()
    sel = df[(df["date"] >= start) & (df["date"] <= end)]
    if sel.empty:
        return _empty(
            f"Tidak ada transaksi pada {start_date} s/d {end_date}. {_range_hint()}"
        )

    by_cat = (
        sel.groupby("category")["total_amount"]
        .agg(total="sum", transactions="count")
        .to_dict("index")
    )
    return _ok({
        "period": f"{start_date} s/d {end_date}",
        "total_amount": int(sel["total_amount"].sum()),
        "transactions": int(len(sel)),
        "by_category": {k: {"total": int(v["total"]), "transactions": int(v["transactions"])}
                        for k, v in by_cat.items()},
    })


def get_top_products(n: int = 5) -> dict:
    """Top-n products by revenue (whole dataset)."""
    if not isinstance(n, int) or n < 1:
        return _error(f"Parameter n harus bilangan bulat >= 1, diterima: {n!r}")

    df = _load()
    top = (
        df.groupby(["product_name", "category"])["total_amount"]
        .agg(total_revenue="sum", transactions="count")
        .sort_values("total_revenue", ascending=False)
        .head(n)
        .reset_index()
    )
    return _ok({
        "ranking": [
            {
                "rank": i + 1,
                "product": r["product_name"],
                "category": r["category"],
                "total_revenue": int(r["total_revenue"]),
                "transactions": int(r["transactions"]),
            }
            for i, r in top.iterrows()
        ]
    })


def calculate_growth(product: str, period1: list, period2: list) -> dict:
    """Percent change in sales of a product OR category between two periods.

    period1/period2: [start_date, end_date] as YYYY-MM-DD strings.
    """
    df = _load()

    # accept a product name OR a category name
    if product in set(df["category"]):
        mask = df["category"] == product
        subject_type = "category"
    elif product in set(df["product_name"]):
        mask = df["product_name"] == product
        subject_type = "product"
    else:
        suggestions = _suggest_products(product)
        cats = sorted(set(df["category"]))
        return _error(
            f"'{product}' tidak ditemukan sebagai produk maupun kategori. "
            f"Mungkin maksudmu: {', '.join(suggestions)}. "
            f"Kategori yang valid: {', '.join(cats)}."
        )

    totals = []
    for label, period in (("period1", period1), ("period2", period2)):
        if not (isinstance(period, (list, tuple)) and len(period) == 2):
            return _error(f"{label} harus berupa [start_date, end_date]. Diterima: {period!r}")
        start, end, err = _validate_dates(period[0], period[1])
        if err:
            return err
        sel = df[mask & (df["date"] >= start) & (df["date"] <= end)]
        totals.append(int(sel["total_amount"].sum()))

    p1, p2 = totals
    if p1 == 0:
        return _error(
            f"Penjualan '{product}' pada period1 = 0, persentase pertumbuhan tidak "
            f"terdefinisi (pembagian nol). Nilai absolut period2: Rp {p2:,}. "
            f"Laporkan sebagai nilai absolut, bukan persentase."
        )

    growth = (p2 - p1) / p1 * 100
    return _ok({
        "subject": product,
        "subject_type": subject_type,
        "period1_total": p1,
        "period2_total": p2,
        "growth_percent": round(growth, 2),
        "direction": "naik" if growth > 0 else ("turun" if growth < 0 else "stabil"),
    })


# ---------- safe dispatch layer (called by the agent loop) ----------

TOOL_REGISTRY = {
    "get_sales_by_period": get_sales_by_period,
    "get_top_products": get_top_products,
    "calculate_growth": calculate_growth,
}


def execute_tool_safely(tool_name: str, tool_args: dict) -> dict:
    """Dispatch + last-resort protection. Exceptions become observations."""
    fn = TOOL_REGISTRY.get(tool_name)
    if fn is None:
        return _error(
            f"Tool '{tool_name}' tidak dikenal. Tool yang tersedia: "
            f"{', '.join(TOOL_REGISTRY)}"
        )
    try:
        return fn(**tool_args)
    except TypeError as e:
        return _error(f"Argumen tidak cocok untuk {tool_name}: {e}")
    except Exception as e:  # last resort: observation, not crash
        return _error(f"Kesalahan tak terduga di {tool_name}: {type(e).__name__}: {e}")
