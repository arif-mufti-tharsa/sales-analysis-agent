# Design Decisions / Keputusan Desain

> Dokumen ini menjelaskan **alasan** di balik setiap keputusan desain — bukan hanya apa yang dibangun, tapi kenapa. Ditulis dalam Bahasa Indonesia; istilah teknis tetap dalam English.

## 1. Planning Loop: Single ReAct Loop

**Keputusan:** satu loop tunggal — LLM melihat conversation history → memutuskan memanggil tool atau menjawab final → hasil tool masuk kembali ke history → ulang. State = list of messages. Maksimal 5 iterasi.

**Reasoning:** kompleksitas loop harus proporsional dengan *ruang aksi* agent. Proyek ini punya 3 tools deterministik atas 793 baris data — tidak ada rencana multi-langkah yang cukup rumit untuk membutuhkan planner-executor terpisah, multi-agent, atau state machine framework. Kekuatan ReAct bukan di arsitektur loop-nya (loop-nya trivial), melainkan di fakta bahwa **setiap observasi masuk kembali ke context** sehingga LLM bisa self-correct. Kualitas agent ~80% ditentukan oleh kualitas deskripsi tool dan pesan yang dikembalikan tool.

**Sengaja TIDAK dipakai (dan kenapa):**

| Tidak dipakai | Alasan |
|---|---|
| Plan-and-execute (planner terpisah) | Ruang aksi terlalu kecil; menambah permukaan debugging tanpa menambah kemampuan |
| Multi-agent orchestration | Satu domain, satu dataset — tidak ada pembagian kerja yang berarti |
| Vector DB / RAG memory | 793 baris muat di pandas DataFrame; retrieval tidak diperlukan |
| Framework berat (LangGraph penuh, dsb.) | Tujuan proyek: memahami mekanisme dasarnya, bukan memakai abstraksi orang lain |

## 2. Stopping Conditions

Tiga jenis, ketiganya diperlukan:

1. **Natural stop** — LLM merespons tanpa tool call → itu jawaban final. Mekanisme utama; model dengan function calling sudah dilatih berhenti saat informasi cukup.
2. **Budget stop** — `MAX_ITERATIONS = 5`. Pertanyaan tersulit ("bandingkan Mei vs Juni semua kategori") butuh ~3–4 calls. Saat budget habis, agent TIDAK error — ia menjawab dengan informasi yang terkumpul + menyebut keterbatasannya. *Alasan:* failure mode klasik agent adalah memanggil tool yang sama berulang-ulang; tanpa budget = loop tak berujung dan biaya API tak terkendali.
3. **Uncertainty stop** — minta klarifikasi *sebelum* memanggil tool jika ambiguitas mengubah pilihan tool/parameter DAN mahal untuk dijawab semua interpretasinya. Jika data tidak tersedia (mis. pertanyaan soal Juli, data berhenti di Juni): jawab jujur, bukan menebak. Di-enforce lewat system prompt, bukan kode.

## 3. Fallback Design: Errors Are Observations

**Prinsip: konsumen output tool adalah LLM.** Empty dict = observasi tidak informatif → LLM mengarang interpretasi (halusinasi). Pesan error deskriptif = observasi *actionable* → LLM self-correct di iterasi berikutnya.

Tiga lapis:

1. **Structured return** — semua tool mengembalikan `{status: "ok"|"empty"|"error", data, message}`. Pesan empty/error selalu menyebutkan cara memperbaiki: rentang tanggal valid, saran nama produk mirip ("did you mean?").
2. **Validasi input di dalam tool** — tanggal parseable & dalam rentang data (2026-04-01 s/d 2026-06-30), produk ada di dataset, pembagian nol di `calculate_growth` saat penjualan period1 = 0.
3. **try/except di loop** — exception tak terduga diubah jadi observasi teks, bukan crash.

**Sengaja TIDAK dibangun:** retry framework, exponential backoff, circuit breaker. Cukup satu aturan di system prompt: tool sama gagal 2x dengan error sama → berhenti mencoba, jelaskan ke user.

## 4. Ambiguity Handling

Studi kasus: *"Kategori apa paling menguntungkan?"* — bisa berarti jumlah transaksi ATAU total omzet.

**Rule of thumb: bandingkan biaya menjawab semua interpretasi vs biaya bertanya balik.**

- Kedua interpretasi murah (1–2 tool calls, tanpa efek samping) → **jawab keduanya dengan label eksplisit**: "Dari sisi omzet: HP tertinggi. Dari sisi jumlah transaksi: Aksesoris terbanyak."
- Bertanya balik hanya jika: interpretasi >3, mahal dieksekusi, atau aksinya irreversible.
- Asumsi diam-diam = opsi terburuk — user tidak tahu jawabannya menjawab pertanyaan yang mana.

Catatan kejujuran data: "menguntungkan" secara harfiah = *profit*, dan dataset tidak punya kolom cost. Agent menambahkan disclaimer "omzet bukan profit karena data biaya tidak tersedia."

## 5. Pseudocode

```
FUNCTION run_agent(user_question):
    messages = [SYSTEM_PROMPT, user_question]

    FOR iteration FROM 1 TO MAX_ITERATIONS:
        response = LLM(messages, tools=TOOL_SCHEMAS)
        append response to messages

        IF response contains NO tool_call:
            RETURN response.text                    # natural stop

        FOR each tool_call IN response:
            observation = execute_tool_safely(tool_call)
            append observation (as tool result) to messages

    # budget stop
    append instruction: "jawab dengan info yang ada + sebutkan keterbatasan"
    RETURN LLM(messages, tools=NONE)


FUNCTION execute_tool_safely(tool_call):
    validate params:
        dates parseable & within DATA_RANGE  → else error + rentang valid
        product exists in dataset            → else error + saran produk mirip
    TRY:
        result = call actual function
        IF result empty:
            RETURN {status:"empty", message: "... dataset covers April-June 2026"}
        RETURN {status:"ok", data: result}
    CATCH e:
        RETURN {status:"error", message: string(e)}
```

## 6. Scope: Portfolio, Not Production

Yang membedakan proyek ini dari production system (dan sengaja di-scope keluar): observability/tracing, eval suite otomatis, guardrails berlapis, concurrency, caching. Pola intinya — loop sederhana + structured tool results + kebijakan di system prompt — tetap sama di production; yang berubah hanya lapisan di sekitarnya.
