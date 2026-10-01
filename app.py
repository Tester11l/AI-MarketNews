"""
IDX News AI — berita Indonesia dari Yahoo Finance + analisis dampak ke market.
Data: Yahoo Finance (yfinance) | Analisis: Google Gemini (REST API)
"""

import os
import html
from datetime import datetime

import requests
import streamlit as st
import yfinance as yf

st.set_page_config(page_title="IDX News AI", page_icon="📊", layout="wide")

# ============================================================
# STYLE — dark, kalem, nggak mencolok
# ============================================================
st.markdown(
    """
<style>
.block-container {padding-top: 2.2rem; max-width: 1100px;}
h1, h2, h3 {font-weight: 600; letter-spacing: -0.01em;}
footer {visibility: hidden;}
[data-testid="stSidebar"] {border-right: 1px solid #1f252d;}

.news-card {
    background: #141920; border: 1px solid #232a33; border-radius: 10px;
    padding: 14px 16px; margin-bottom: 10px; transition: border-color .15s;
}
.news-card:hover {border-color: #374250;}
.news-card a {
    color: #cfd8e3; text-decoration: none; font-weight: 500;
    font-size: 0.97rem; line-height: 1.45;
}
.news-card a:hover {color: #93b5d6;}
.news-meta {color: #7d8793; font-size: 0.78rem; margin-top: 6px;}

.subtle {color: #8a94a0; font-size: 0.9rem;}
.price-big {font-size: 2.1rem; font-weight: 600; line-height: 1.1;}
.chg-up {color: #6fb38a; font-size: 0.95rem;}
.chg-down {color: #c47b7b; font-size: 0.95rem;}
.chg-flat {color: #8a94a0; font-size: 0.95rem;}
</style>
""",
    unsafe_allow_html=True,
)

# ============================================================
# DAFTAR SAHAM (kode IDX tanpa .JK — suffix ditambah otomatis)
# ============================================================
STOCKS = {
    # Perbankan
    "BBCA": "Bank Central Asia", "BBRI": "Bank Rakyat Indonesia", "BMRI": "Bank Mandiri",
    "BBNI": "Bank Negara Indonesia", "BRIS": "Bank Syariah Indonesia", "BBTN": "Bank Tabungan Negara",
    "BNGA": "Bank CIMB Niaga", "BDMN": "Bank Danamon", "BTPS": "Bank BTPN Syariah",
    "ARTO": "Bank Jago", "BJBR": "Bank BJB", "BJTM": "Bank Jatim", "MEGA": "Bank Mega",
    "NISP": "Bank OCBC NISP", "PNBN": "Bank Pan Indonesia", "BNLI": "Bank Permata", "BBYB": "Bank Neo Commerce",
    # Telekomunikasi & teknologi
    "TLKM": "Telkom Indonesia", "ISAT": "Indosat Ooredoo Hutchison", "EXCL": "XL Axiata",
    "MTEL": "Dayamitra Telekomunikasi", "TOWR": "Sarana Menara Nusantara", "TBIG": "Tower Bersama Infrastructure",
    "GOTO": "GoTo Gojek Tokopedia", "BUKA": "Bukalapak", "EMTK": "Elang Mahkota Teknologi",
    "DCII": "DCI Indonesia", "WIFI": "Solusi Sinergi Digital", "MLPT": "Multipolar Technology",
    # Konsumer & ritel
    "UNVR": "Unilever Indonesia", "ICBP": "Indofood CBP", "INDF": "Indofood Sukses Makmur",
    "MYOR": "Mayora Indah", "SIDO": "Sido Muncul", "GGRM": "Gudang Garam", "HMSP": "HM Sampoerna",
    "CPIN": "Charoen Pokphand Indonesia", "JPFA": "Japfa Comfeed", "MAIN": "Malindo Feedmill",
    "AMRT": "Sumber Alfaria Trijaya", "MIDI": "Midi Utama Indonesia", "MAPI": "Mitra Adiperkasa",
    "MAPA": "MAP Aktif Adiperkasa", "ACES": "Aspirasi Hidup Indonesia", "ERAA": "Erajaya Swasembada",
    "LPPF": "Matahari Department Store", "ULTJ": "Ultrajaya Milk", "CMRY": "Cisarua Mountain Dairy",
    # Kesehatan
    "KLBF": "Kalbe Farma", "MIKA": "Mitra Keluarga Karyasehat", "SILO": "Siloam Hospitals",
    "HEAL": "Medikaloka Hermina", "KAEF": "Kimia Farma", "TSPC": "Tempo Scan Pacific",
    # Energi
    "ADRO": "Alamtri Resources Indonesia", "AADI": "Adaro Andalan Indonesia", "ADMR": "Adaro Minerals Indonesia",
    "PTBA": "Bukit Asam", "ITMG": "Indo Tambangraya Megah", "BYAN": "Bayan Resources",
    "INDY": "Indika Energy", "HRUM": "Harum Energy", "BUMI": "Bumi Resources",
    "MEDC": "Medco Energi Internasional", "PGAS": "Perusahaan Gas Negara", "AKRA": "AKR Corporindo",
    "ELSA": "Elnusa", "PGEO": "Pertamina Geothermal Energy", "BREN": "Barito Renewables Energy",
    "CUAN": "Petrindo Jaya Kreasi", "PTRO": "Petrosea", "ENRG": "Energi Mega Persada",
    "BSSR": "Baramulti Suksessarana", "TOBA": "TBS Energi Utama", "DOID": "Delta Dunia Makmur",
    # Pertambangan logam
    "ANTM": "Aneka Tambang", "INCO": "Vale Indonesia", "MDKA": "Merdeka Copper Gold",
    "AMMN": "Amman Mineral Internasional", "MBMA": "Merdeka Battery Materials", "NCKL": "Trimegah Bangun Persada",
    "TINS": "Timah", "BRMS": "Bumi Resources Minerals", "PSAB": "J Resources Asia Pasifik",
    # Industri, otomotif, petrokimia, kertas
    "ASII": "Astra International", "UNTR": "United Tractors", "AUTO": "Astra Otoparts",
    "SMSM": "Selamat Sempana Perkasa", "IMAS": "Indomobil Sukses Internasional", "GJTL": "Gajah Tunggal",
    "BRPT": "Barito Pacific", "TPIA": "Chandra Asri Pacific", "ESSA": "ESSA Industries Indonesia",
    "INKP": "Indah Kiat Pulp & Paper", "TKIM": "Pabrik Kertas Tjiwi Kimia", "ARNA": "Arwana Citramulia",
    "HEXA": "Hexindo Adiperkasa", "MPMX": "Mitra Pinasthika Mustika", "SRTG": "Saratoga Investama Sedaya",
    # Semen, konstruksi, infrastruktur
    "SMGR": "Semen Indonesia", "INTP": "Indocement Tunggal Prakarsa", "WIKA": "Wijaya Karya",
    "PTPP": "PP (Persero)", "ADHI": "Adhi Karya", "JSMR": "Jasa Marga", "WSKT": "Waskita Karya",
    "TOTL": "Total Bangun Persada",
    # Properti
    "BSDE": "Bumi Serpong Damai", "CTRA": "Ciputra Development", "PWON": "Pakuwon Jati",
    "SMRA": "Summarecon Agung", "ASRI": "Alam Sutera Realty", "LPKR": "Lippo Karawaci",
    "JRPT": "Jaya Real Property", "DMAS": "Puradelta Lestari", "KIJA": "Kawasan Industri Jababeka",
    "PANI": "Pantai Indah Kapuk Dua", "MKPI": "Metropolitan Kentjana",
    # Agribisnis
    "AALI": "Astra Agro Lestari", "LSIP": "PP London Sumatra", "SSMS": "Sawit Sumbermas Sarana",
    "TAPG": "Triputra Agro Persada", "DSNG": "Dharma Satya Nusantara", "SMAR": "Sinar Mas Agro Resources",
    "SGRO": "Sampoerna Agro",
    # Media & transportasi
    "SCMA": "Surya Citra Media", "MNCN": "Media Nusantara Citra", "BIRD": "Blue Bird",
    "ASSA": "Adi Sarana Armada", "SMDR": "Samudera Indonesia", "GIAA": "Garuda Indonesia",
    "AVIA": "Avia Avian",
}
STOCK_OPTIONS = sorted(STOCKS.keys())
INDEX_TICKER = "^JKSE"  # IHSG

# ============================================================
# LLM — Gemini via REST (error aslinya ditampilkan)
# ============================================================
GEMINI_MODELS = ["gemini-2.5-flash", "gemini-flash-latest", "gemini-2.0-flash"]


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default) or default).strip()
    except Exception:
        return os.environ.get(name, default).strip()


def call_llm(prompt: str):
    """Return (ok: bool, teks_atau_error: str)."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return False, "GEMINI_API_KEY belum kebaca. Cek nama variabelnya di Secrets (harus persis GEMINI_API_KEY)."

    custom_model = get_secret("GEMINI_MODEL")
    models = [custom_model] if custom_model else GEMINI_MODELS
    errors = []

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        try:
            r = requests.post(
                url,
                headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                json={
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.4, "maxOutputTokens": 1500},
                },
                timeout=60,
            )
        except Exception as e:
            errors.append(f"{model}: gagal konek ({e})")
            continue

        if r.status_code == 200:
            try:
                parts = r.json()["candidates"][0]["content"]["parts"]
                text = "".join(p.get("text", "") for p in parts).strip()
                if text:
                    return True, text
                errors.append(f"{model}: respons kosong")
            except Exception:
                errors.append(f"{model}: respons kosong/diblokir")
            continue

        try:
            msg = r.json().get("error", {}).get("message", r.text[:200])
        except Exception:
            msg = r.text[:200]
        errors.append(f"{model}: HTTP {r.status_code} — {msg}")

        # key salah/ditolak → ganti model nggak bakal bantu
        if r.status_code in (401, 403) or "API key" in msg:
            break

    return False, "\n".join(errors)


# ============================================================
# DATA
# ============================================================
@st.cache_data(ttl=3600)
def search_other_stocks(query: str, max_results: int = 12):
    """Cari saham IDX di luar daftar bawaan lewat search Yahoo Finance."""
    if not query or len(query.strip()) < 2:
        return []
    found = []
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": max_results * 2, "newsCount": 0},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=6,
        )
        for q in resp.json().get("quotes", []):
            sym = q.get("symbol", "")
            if sym.endswith(".JK"):
                found.append((sym.replace(".JK", ""), q.get("shortname") or q.get("longname") or sym))
    except Exception:
        pass
    return found[:max_results]


@st.cache_data(ttl=600)
def get_news(symbol: str, limit: int = 10):
    try:
        news = yf.Ticker(symbol).news or []
    except Exception:
        return []
    out = []
    for item in news:
        c = item.get("content", item)
        title = c.get("title") or item.get("title", "")
        if not title:
            continue
        out.append({
            "title": title,
            "link": (c.get("canonicalUrl") or {}).get("url") or item.get("link", ""),
            "publisher": (c.get("provider") or {}).get("displayName") or item.get("publisher", ""),
            "date": c.get("pubDate") or "",
        })
    out.sort(key=lambda n: n["date"], reverse=True)  # terbaru di atas
    return out[:limit]


@st.cache_data(ttl=600)
def get_history(symbol: str, period: str = "3mo"):
    try:
        h = yf.Ticker(symbol).history(period=period)
        return h if not h.empty else None
    except Exception:
        return None


def fmt_date(s: str) -> str:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M")
    except Exception:
        return s


def render_news(items):
    if not items:
        st.markdown('<div class="subtle">Belum ada berita ditemukan di Yahoo Finance untuk ini.</div>',
                    unsafe_allow_html=True)
        return
    for n in items:
        st.markdown(
            f"""<div class="news-card">
<a href="{html.escape(n['link'])}" target="_blank">{html.escape(n['title'])}</a>
<div class="news-meta">{html.escape(n['publisher'])} · {html.escape(fmt_date(n['date']))}</div>
</div>""",
            unsafe_allow_html=True,
        )


def render_price(symbol: str):
    hist = get_history(symbol)
    if hist is None or len(hist) < 2:
        return
    last, prev = hist["Close"].iloc[-1], hist["Close"].iloc[-2]
    chg = (last - prev) / prev * 100 if prev else 0
    cls = "chg-up" if chg > 0 else "chg-down" if chg < 0 else "chg-flat"
    arrow = "▲" if chg > 0 else "▼" if chg < 0 else "–"
    st.markdown(
        f'<div class="price-big">Rp {last:,.0f}</div>'
        f'<div class="{cls}">{arrow} {chg:+.2f}% dari penutupan sebelumnya</div>',
        unsafe_allow_html=True,
    )
    st.line_chart(hist["Close"], height=200, color="#6f8fb0")


def run_analysis(subject: str, news_items: list):
    if not news_items:
        st.info("Tidak ada berita untuk dianalisis.")
        return
    news_text = "\n".join(f"- {n['title']} ({n['publisher']}, {fmt_date(n['date'])})" for n in news_items)
    prompt = f"""Kamu analis pasar modal Indonesia yang ringkas dan lugas.

Berita terbaru terkait {subject}:
{news_text}

Buat analisis dalam Bahasa Indonesia (maks 180 kata):
1. Ringkasan isu utama
2. Sentimen keseluruhan (positif/negatif/netral) + alasannya
3. Potensi dampak ke harga saham / IHSG

Langsung ke analisis, tanpa disclaimer panjang."""
    with st.spinner("Menganalisis..."):
        ok, result = call_llm(prompt)
    with st.container(border=True):
        st.markdown("**Analisis dampak**")
        if ok:
            st.markdown(result)
        else:
            st.error("LLM gagal dipanggil. Detail error:")
            st.code(result)


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### IDX News AI")
    st.markdown('<div class="subtle">Berita Yahoo Finance + analisis dampak ke market.</div>',
                unsafe_allow_html=True)
    st.divider()

    st.markdown("**Pilih saham**")
    code = st.selectbox(
        "Kode saham",
        STOCK_OPTIONS,
        index=STOCK_OPTIONS.index("BBCA"),
        format_func=lambda c: f"{c} · {STOCKS[c]}",
        label_visibility="collapsed",
        help="Klik lalu ketik kode atau nama untuk mencari.",
    )
    names = dict(STOCKS)

    with st.expander("Saham tidak ada di daftar?"):
        q = st.text_input("Cari nama / kode", placeholder="contoh: sampoerna, MDKA")
        hits = search_other_stocks(q) if q else []
        if q and not hits:
            st.caption("Tidak ketemu di Yahoo Finance.")
        if hits:
            for c, n in hits:
                names[c] = n
            code = st.radio(
                "Hasil", [c for c, _ in hits],
                format_func=lambda c: f"{c} · {names[c]}",
                label_visibility="collapsed",
            )

    st.divider()
    with st.expander("Tes koneksi LLM"):
        if st.button("Tes sekarang", use_container_width=True):
            with st.spinner("Menghubungi Gemini..."):
                ok, res = call_llm("Balas dengan satu kata: OK")
            if ok:
                st.success(f"Terhubung. Respons: {res[:40]}")
            else:
                st.error("Gagal")
                st.code(res)

# ============================================================
# MAIN
# ============================================================
tab_stock, tab_market = st.tabs(["Saham", "Pasar (IHSG)"])

with tab_stock:
    symbol = f"{code}.JK"
    st.markdown(f"## {code}")
    st.markdown(f'<div class="subtle">{html.escape(names.get(code, code))} · IDX</div>',
                unsafe_allow_html=True)
    st.write("")

    left, right = st.columns([1, 1.3], gap="large")
    with left:
        render_price(symbol)
    with right:
        news = get_news(symbol)
        st.markdown("**Berita terbaru**")
        render_news(news)
        if news and st.button("Analisis dampak", key=f"an_{code}"):
            run_analysis(f"saham {names.get(code, code)} ({code})", news)

with tab_market:
    st.markdown("## IHSG")
    st.markdown('<div class="subtle">Berita pasar & ekonomi Indonesia</div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        render_price(INDEX_TICKER)
    with right:
        idx_news = get_news(INDEX_TICKER, limit=12)
        st.markdown("**Berita terbaru**")
        render_news(idx_news)
        if idx_news and st.button("Analisis dampak ke IHSG", key="an_ihsg"):
            run_analysis("IHSG / pasar saham Indonesia", idx_news)

st.write("")
st.markdown(
    f'<div class="subtle">Data: Yahoo Finance · cache 10 menit · {datetime.now().strftime("%H:%M:%S")}</div>',
    unsafe_allow_html=True,
)
