"""Generate the synthetic sales dataset (seeded => reproducible).

793 transactions, 2026-04-01 .. 2026-06-30, 3 categories.
Built-in story for the demo questions: HP sales PEAK in May
(promo season) then DROP in June, so "why did phone sales fall?"
has a real answer in the data.

Run: python scripts/generate_data.py
"""

import random
from datetime import date, timedelta

import pandas as pd

random.seed(42)

PRODUCTS = {
    "HP": [
        ("Samsung Galaxy A55", 5_999_000),
        ("Xiaomi Redmi Note 13", 3_499_000),
        ("iPhone 15", 13_999_000),
        ("Oppo Reno 11", 5_499_000),
        ("Vivo V30", 4_999_000),
        ("Samsung Galaxy S24", 12_999_000),
    ],
    "Aksesoris": [
        ("Casing HP Premium", 149_000),
        ("Tempered Glass", 75_000),
        ("Charger 65W GaN", 349_000),
        ("TWS Earbuds X1", 499_000),
        ("Powerbank 10000mAh", 299_000),
        ("Kabel USB-C 2m", 89_000),
    ],
    "Elektronik Rumah": [
        ("Rice Cooker 1.8L", 425_000),
        ("Kipas Angin Tornado", 315_000),
        ("Blender Multifungsi", 389_000),
        ("Setrika Uap", 275_000),
        ("Air Fryer 4L", 899_000),
        ("Smart TV 43 inch", 4_299_000),
    ],
}

# transactions per (month, category) -- sums to 793.
# Story: HP promo in May (spike), normal-ish June => visible drop.
PLAN = {
    (4, "HP"): 70,  (4, "Aksesoris"): 118, (4, "Elektronik Rumah"): 72,   # Apr 260
    (5, "HP"): 105, (5, "Aksesoris"): 116, (5, "Elektronik Rumah"): 64,   # May 285
    (6, "HP"): 58,  (6, "Aksesoris"): 122, (6, "Elektronik Rumah"): 68,   # Jun 248
}

DAYS_IN = {4: 30, 5: 31, 6: 30}

rows = []
for (month, category), count in PLAN.items():
    for _ in range(count):
        day = random.randint(1, DAYS_IN[month])
        product, price = random.choice(PRODUCTS[category])
        qty = 1 if category == "HP" else random.choice([1, 1, 1, 2, 2, 3])
        rows.append({
            "date": date(2026, month, day).isoformat(),
            "category": category,
            "product_name": product,
            "unit_price": price,
            "quantity": qty,
            "total_amount": price * qty,
        })

df = pd.DataFrame(rows).sort_values("date").reset_index(drop=True)
assert len(df) == 793, len(df)
df.to_csv("data/sales_data.csv", index=False)
print(f"Wrote data/sales_data.csv: {len(df)} rows")
print(df.groupby([df.date.str[:7], "category"])["total_amount"].agg(["count", "sum"]))
