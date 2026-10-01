"""
IDX News AI — Analisis berita Indonesia & dampaknya ke market, per saham.

Sumber data: Yahoo Finance (via yfinance)
Sumber analisis: LLM (default: Google Gemini, bisa diganti ke Claude API)
"""

import streamlit as st
import yfinance as yf
import requests
from datetime import datetime
import time

# ============================================================
# KONFIGURASI
# ============================================================

st.set_page_config(page_title="IDX News AI", page_icon="📈", layout="wide")

# Cuma shortcut/tombol cepat — cakupan saham TIDAK dibatasi ke list ini.
# User bisa cari & pilih SEMUA saham Indonesia lewat fitur search di bawah
# (search langsung ke Yahoo Finance, cover semua saham IDX yang ada di sana).
QUICK_ACCESS = {
    "BBCA.JK": "Bank Central Asia",
    "BBRI.JK": "Bank Rakyat Indonesia",
    "BMRI.JK": "Bank Mandiri",
    "TLKM.JK": "Telkom Indonesia",
    "ASII.JK": "Astra International",
    "UNVR.JK": "Unilever Indonesia",
    "ICBP.JK": "Indofood CBP",
    "ADRO.JK": "Adaro Energy",
    "ANTM.JK": "Aneka Tambang",
    "GOTO.JK": "GoTo Gojek Tokopedia",
}

INDEX_TICKER = "^JKSE"  # IHSG

# ============================================================
# LLM BACKEND — ganti fungsi ini kalau mau pindah provider
# ============================================================

def call_llm(prompt: str) -> str:
    """
    Panggil LLM buat analisis. Default pakai Google Gemini (free tier).
    Butuh GEMINI_API_KEY di Streamlit secrets.

    Kalau mau pakai Claude API, ganti isi fungsi ini (contoh ada di bawah,
    tinggal uncomment & comment yang Gemini).
    """
    try:
        import google.generativeai as genai
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return "⚠️ GEMINI_API_KEY belum diset di Streamlit secrets."
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"⚠️ Gagal memanggil LLM: {e}"

    # --- Alternatif: pakai Claude API ---
    # import anthropic
    # api_key = st.secrets.get("ANTHROPIC_API_KEY", "")
    # client = anthropic.Anthropic(api_key=api_key)
    # msg = client.messages.create(
    #     model="claude-sonnet-4-6",
    #     max_tokens=600,
    #     messages=[{"role": "user", "content": prompt}]
    # )
    # return msg.content[0].text


# ============================================================
# FUNGSI SEARCH SAHAM — cover SEMUA saham Indonesia di Yahoo Finance
# ============================================================

@st.cache_data(ttl=3600)
def search_indonesian_stocks(query: str, max_results: int = 15):
    """
    Cari saham Indonesia (kode/nama) langsung ke Yahoo Finance search.
    Nggak dibatasi list manual — otomatis cover semua saham IDX yang
    terindex di Yahoo Finance.
    """
    if not query or len(query.strip()) < 2:
        return []

    results = []

    # Cara 1: pakai yfinance.Search (kalau versi yfinance mendukung)
    try:
        from yfinance import Search
        s = Search(query, max_results=max_results * 2)
        for q in (s.quotes or []):
            symbol = q.get("symbol", "")
            if symbol.endswith(".JK"):
                results.append({
                    "symbol": symbol,
                    "name": q.get("shortname") or q.get("longname") or symbol,
                })
    except Exception:
        pass

    # Cara 2 (fallback): hit endpoint search Yahoo Finance langsung
    if not results:
        try:
            resp = requests.get(
                "https://query2.finance.yahoo.com/v1/finance/search",
                params={"q": query, "quotesCount": max_results * 2, "newsCount": 0},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=6,
            )
            data = resp.json()
            for q in data.get("quotes", []):
                symbol = q.get("symbol", "")
                if symbol.endswith(".JK"):
                    results.append({
                        "symbol": symbol,
                        "name": q.get("shortname") or q.get("longname") or symbol,
                    })
        except Exception:
            pass

    # Dedup & limit
    seen = set()
    deduped = []
    for r in results:
        if r["symbol"] not in seen:
            seen.add(r["symbol"])
            deduped.append(r)
    return deduped[:max_results]


# ============================================================
# FUNGSI AMBIL DATA
# ============================================================

@st.cache_data(ttl=600)  # cache 10 menit biar nggak spam request
def get_news(ticker_symbol: str, limit: int = 8):
    """Ambil berita terbaru untuk sebuah ticker dari Yahoo Finance."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        news = ticker.news or []
        cleaned = []
        for item in news[:limit]:
            content = item.get("content", item)  # yfinance versi baru nest di "content"
            title = content.get("title") or item.get("title", "")
            link = (content.get("canonicalUrl", {}) or {}).get("url") or item.get("link", "")
            publisher = (content.get("provider", {}) or {}).get("displayName") or item.get("publisher", "")
            pub_date = content.get("pubDate") or ""
            if title:
                cleaned.append({
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "date": pub_date,
                })
        return cleaned
    except Exception as e:
        st.warning(f"Gagal ambil berita untuk {ticker_symbol}: {e}")
        return []


@st.cache_data(ttl=600)
def get_price_snapshot(ticker_symbol: str):
    """Ambil harga terakhir & perubahan harian."""
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="5d")
        if hist.empty:
            return None
        last_close = hist["Close"].iloc[-1]
        prev_close = hist["Close"].iloc[-2] if len(hist) > 1 else last_close
        change_pct = ((last_close - prev_close) / prev_close) * 100
        return {"price": last_close, "change_pct": change_pct}
    except Exception:
        return None


def analyze_news_impact(company_name: str, news_list: list) -> str:
    """Minta LLM meringkas berita & menilai potensi dampak ke saham/market."""
    if not news_list:
        return "Tidak ada berita terbaru yang bisa dianalisis."

    news_text = "\n".join(
        f"- {n['title']} (sumber: {n['publisher']})" for n in news_list
    )

    prompt = f"""Kamu adalah analis pasar modal Indonesia yang ringkas dan lugas.

Berikut daftar berita terbaru terkait {company_name}:
{news_text}

Tolong buat analisis singkat dalam Bahasa Indonesia (maks 150 kata) yang mencakup:
1. Ringkasan isu utama dari berita-berita di atas
2. Sentimen keseluruhan (positif/negatif/netral)
3. Potensi dampak ke harga saham atau ke IHSG secara umum

Jangan beri disclaimer panjang, langsung ke analisisnya."""

    return call_llm(prompt)


# ============================================================
# UI
# ============================================================

st.title("📈 IDX News AI")
st.caption("Berita terbaru Indonesia dari Yahoo Finance + analisis dampak ke market, per saham.")

tab1, tab2 = st.tabs(["🌏 Berita & Dampak Umum (IHSG)", "🏢 Berita per Saham"])

# --- TAB 1: Berita umum / index ---
with tab1:
    st.subheader("Berita seputar IHSG / Ekonomi Indonesia")
    if st.button("🔄 Refresh berita IHSG", key="refresh_ihsg"):
        get_news.clear()

    index_news = get_news(INDEX_TICKER, limit=10)

    if not index_news:
        st.info("Belum ada berita ditemukan untuk IHSG lewat ticker ini. "
                 "Yahoo Finance kadang membatasi berita general index — "
                 "coba cek tab per saham untuk berita yang lebih lengkap.")
    else:
        for n in index_news:
            with st.container(border=True):
                st.markdown(f"**[{n['title']}]({n['link']})**")
                st.caption(f"{n['publisher']} · {n['date']}")

        if st.button("🤖 Analisis dampak ke IHSG", key="analyze_ihsg"):
            with st.spinner("Menganalisis..."):
                result = analyze_news_impact("IHSG / pasar saham Indonesia", index_news)
            st.markdown("### Hasil Analisis")
            st.write(result)

# --- TAB 2: Berita per saham ---
with tab2:
    col1, col2 = st.columns([1, 2])

    with col1:
        st.markdown("**Cari saham (semua saham IDX yang ada di Yahoo Finance)**")
        query = st.text_input(
            "Ketik nama atau kode saham",
            placeholder="contoh: bank, MDKA, telkom, semen...",
        )

        # Hasil pencarian real-time ke Yahoo Finance
        search_results = search_indonesian_stocks(query) if query else []

        # Kalau belum search apa-apa, tampilin quick access sebagai default
        options = {}
        if search_results:
            for r in search_results:
                options[r["symbol"]] = r["name"]
        else:
            options = dict(QUICK_ACCESS)
            st.caption("Belum ada pencarian — nih beberapa saham populer (opsional, "
                       "bebas cari saham lain di atas):")

        selected = st.radio(
            "Pilih dari hasil",
            options=list(options.keys()),
            format_func=lambda x: f"{x} — {options[x]}",
        )

        st.divider()
        manual_code = st.text_input(
            "Atau kalau tau kode pastinya, input manual",
            placeholder="contoh: MDKA.JK",
        )
        if manual_code:
            code = manual_code.strip().upper()
            if not code.endswith(".JK"):
                code += ".JK"
            selected = code
            options[code] = code

    with col2:
        st.markdown(f"### {selected} — {options.get(selected, selected)}")

        snapshot = get_price_snapshot(selected)
        if snapshot:
            delta_color = "normal" if snapshot["change_pct"] >= 0 else "inverse"
            st.metric(
                "Harga terakhir",
                f"Rp {snapshot['price']:,.0f}",
                f"{snapshot['change_pct']:+.2f}%",
            )

        news_items = get_news(selected, limit=8)

        if not news_items:
            st.info("Tidak ada berita ditemukan untuk saham ini di Yahoo Finance.")
        else:
            for n in news_items:
                with st.container(border=True):
                    st.markdown(f"**[{n['title']}]({n['link']})**")
                    st.caption(f"{n['publisher']} · {n['date']}")

            if st.button(f"🤖 Analisis dampak untuk {selected}", key=f"analyze_{selected}"):
                with st.spinner("Menganalisis..."):
                    result = analyze_news_impact(options.get(selected, selected), news_items)
                st.markdown("### Hasil Analisis")
                st.write(result)

st.divider()
st.caption(
    f"Data diambil dari Yahoo Finance via yfinance. Terakhir refresh cache: "
    f"otomatis tiap 10 menit. Timestamp render: {datetime.now().strftime('%H:%M:%S')}"
)
