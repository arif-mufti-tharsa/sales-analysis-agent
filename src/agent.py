"""
ReAct planning loop. Design & pseudocode: docs/design.md.

Run:  python -m src.agent "Bandingkan performa Mei vs Juni untuk semua kategori"
Requires ANTHROPIC_API_KEY in .env (see .env.example).
"""

import json
import sys

from src.tools import DATA_RANGE, execute_tool_safely

MAX_ITERATIONS = 5  # budget stop -- hardest question needs ~3-4 calls
MODEL = "claude-sonnet-5"

SYSTEM_PROMPT = f"""Kamu adalah analis data penjualan untuk toko elektronik & HP.

DATASET: transaksi {DATA_RANGE[0]} s/d {DATA_RANGE[1]} (TIDAK ada data di luar
rentang ini). Kolom: date, category (HP / Aksesoris / Elektronik Rumah),
product_name, unit_price, quantity, total_amount. Mata uang: Rupiah (IDR).

ATURAN:
1. JANGAN PERNAH mengarang angka. Semua angka harus berasal dari hasil tools.
2. Pertanyaan ambigu dengan >=2 interpretasi yang murah (mis. "paling
   menguntungkan" = omzet ATAU jumlah transaksi): jawab SEMUA interpretasi
   dengan label eksplisit, jangan berasumsi diam-diam.
3. Dataset tidak punya data biaya/cost. Jika user bertanya soal profit,
   jelaskan bahwa omzet != profit dan jawab sebatas omzet dengan disclaimer.
4. Jika tool mengembalikan status "error" atau "empty", baca message-nya dan
   perbaiki panggilanmu. Jika tool yang sama gagal 2x dengan error yang sama,
   BERHENTI mencoba dan jelaskan kendalanya ke user dengan jujur.
5. Jika data yang diminta di luar cakupan dataset, katakan itu apa adanya.
6. Jawaban final: ringkas, sebutkan angka kunci, dalam Bahasa Indonesia.
"""

TOOL_SCHEMAS = [
    {
        "name": "get_sales_by_period",
        "description": (
            "Total penjualan dalam rentang tanggal, dengan rincian per kategori "
            "(total omzet + jumlah transaksi). Rentang valid: "
            f"{DATA_RANGE[0]} s/d {DATA_RANGE[1]}."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "YYYY-MM-DD"},
                "end_date": {"type": "string", "description": "YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"],
        },
    },
    {
        "name": "get_top_products",
        "description": "Ranking n produk teratas berdasarkan total omzet (seluruh dataset).",
        "input_schema": {
            "type": "object",
            "properties": {"n": {"type": "integer", "description": "jumlah produk, >= 1"}},
            "required": ["n"],
        },
    },
    {
        "name": "calculate_growth",
        "description": (
            "Persentase perubahan penjualan sebuah PRODUK atau KATEGORI antara dua "
            "periode. period1/period2 = [start_date, end_date]. Berguna untuk "
            "pertanyaan naik/turun antar bulan."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "product": {"type": "string", "description": "nama produk ATAU kategori"},
                "period1": {"type": "array", "items": {"type": "string"}, "description": "[start, end] pembanding"},
                "period2": {"type": "array", "items": {"type": "string"}, "description": "[start, end] terbaru"},
            },
            "required": ["product", "period1", "period2"],
        },
    },
]


def run_agent(user_question: str, verbose: bool = True) -> str:
    import anthropic
    from dotenv import load_dotenv

    load_dotenv()
    client = anthropic.Anthropic()
    messages = [{"role": "user", "content": user_question}]

    for iteration in range(1, MAX_ITERATIONS + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1500,
            system=SYSTEM_PROMPT,
            tools=TOOL_SCHEMAS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        tool_uses = [b for b in response.content if b.type == "tool_use"]
        if not tool_uses:  # ---- natural stop ----
            return "".join(b.text for b in response.content if b.type == "text")

        results = []
        for tu in tool_uses:
            observation = execute_tool_safely(tu.name, dict(tu.input))
            if verbose:
                print(f"[iter {iteration}] {tu.name}({json.dumps(tu.input, ensure_ascii=False)}) "
                      f"-> {observation['status']}", file=sys.stderr)
            results.append({
                "type": "tool_result",
                "tool_use_id": tu.id,
                "content": json.dumps(observation, ensure_ascii=False, default=str),
            })
        messages.append({"role": "user", "content": results})

    # ---- budget stop ----
    messages.append({
        "role": "user",
        "content": (
            "Batas iterasi tercapai. Jawab pertanyaan user sekarang dengan "
            "informasi yang sudah terkumpul, dan sebutkan keterbatasannya."
        ),
    })
    response = client.messages.create(
        model=MODEL, max_tokens=1500, system=SYSTEM_PROMPT, messages=messages
    )
    return "".join(b.text for b in response.content if b.type == "text")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python -m src.agent "pertanyaan bisnis"')
        sys.exit(1)
    print(run_agent(sys.argv[1]))
