# Manual Test Scenarios — Hasil Dry-Run

> **Metode:** tool layer dieksekusi nyata terhadap `data/sales_data.csv` (output di bawah = hasil sebenarnya). Kolom "jawaban final" adalah jawaban yang akan disusun agent dari observasi tersebut — jalankan `python -m src.agent "..."` dengan API key untuk transcript LLM live, lalu perbarui tabel ini.

## S1 — Happy path: "Bandingkan performa Mei vs Juni untuk semua kategori"

Tool calls (2): `get_sales_by_period(2026-05-01, 2026-05-31)` → ok; `get_sales_by_period(2026-06-01, 2026-06-30)` → ok.

| Kategori | Mei (omzet / tx) | Juni (omzet / tx) | Perubahan omzet |
|---|---|---|---|
| HP | Rp 810,4 jt / 105 | Rp 498,9 jt / 58 | **-38,4%** |
| Aksesoris | Rp 54,6 jt / 116 | Rp 49,0 jt / 122 | -10,2% |
| Elektronik Rumah | Rp 127,0 jt / 64 | Rp 124,2 jt / 68 | -2,2% |

**Jawaban final:** total omzet turun dari Rp 992,0 jt (285 tx) ke Rp 672,2 jt (248 tx); penurunan hampir seluruhnya didorong kategori HP (-38,4%), sementara jumlah transaksi Aksesoris justru naik. ✅ Natural stop setelah 2 tool calls.

## S2 — Tanggal di luar range: "Berapa penjualan bulan Juli?"

Tool call: `get_sales_by_period(2026-07-01, 2026-07-31)` →
`{"status": "error", "message": "Periode ... sepenuhnya di luar cakupan data. Dataset mencakup 2026-04-01 s/d 2026-06-30."}`

**Jawaban final:** agent menjawab jujur bahwa data hanya mencakup April–Juni 2026, tanpa mengarang angka. ✅ Error message menyebut rentang valid → observasi actionable.

## S3 — Produk tidak ada: "Growth iPhone 99 Mei vs Juni?"

Call 1: `calculate_growth("iPhone 99", ...)` → error: *"'iPhone 99' tidak ditemukan... Mungkin maksudmu: iPhone 15."*
Call 2 (self-correction): `calculate_growth("iPhone 15", ...)` → ok: **-23,08%** (Rp 182,0 jt → Rp 140,0 jt).

**Jawaban final:** agent mengoreksi diri lewat saran "did you mean", menyebut asumsi koreksinya ke user. ✅ Bukti nilai structured error: 1 iterasi ekstra, bukan halusinasi.

## S4 — Ambigu: "Kategori apa paling menguntungkan?"

Tool call: `get_sales_by_period(2026-04-01, 2026-06-30)` → ok.

**Jawaban final (dua interpretasi, label eksplisit):**
- **Dari sisi omzet:** HP tertinggi — Rp 1,895 M (76,6% dari total Rp 2,473 M).
- **Dari sisi jumlah transaksi:** Aksesoris terbanyak — 356 dari 793 transaksi (44,9%).
- **Disclaimer:** dataset tidak punya data biaya, jadi "omzet" ≠ "profit".

✅ Kedua interpretasi murah → dijawab keduanya, bukan asumsi diam-diam.

## S5 — Di luar kemampuan tools: "Berapa profit margin toko?"

Tidak ada tool yang bisa menjawab (tidak ada kolom cost).

**Jawaban final:** agent menjelaskan data biaya tidak tersedia sehingga profit margin tidak bisa dihitung, dan menawarkan analisis omzet sebagai alternatif. ✅ Uncertainty stop tanpa mengarang angka.

## Bonus — "Kenapa penjualan HP turun bulan ini (Juni) dibanding Mei?"

`calculate_growth("HP", Mei, Juni)` → **-38,43%** (Rp 810,4 jt → Rp 498,9 jt). Dikombinasikan dengan S1: jumlah transaksi HP turun 105 → 58 (-45%), sementara kategori lain relatif stabil → penurunan berasal dari volume unit HP, bukan tren toko keseluruhan. (Dalam data sintetis ini: efek berakhirnya lonjakan promo Mei.)
