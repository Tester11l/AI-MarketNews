"""
IDX News AI — berita multi-sumber (Yahoo Finance + Google News + feed Indonesia)
+ indikator teknikal + chatbot Gemini untuk analisis pasar & saham.
"""

import os
import html
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from urllib.parse import urlencode

import requests
import streamlit as st
import yfinance as yf

from core import (
    compute_technicals, detect_tickers, filter_by_keywords, judge_article,
    merge_news, merge_ranked, parse_rss, technicals_text, trim_text,
)

st.set_page_config(page_title="IDX News AI", page_icon="📊", layout="wide")

# ============================================================
# STYLE — dark, kalem
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
    padding: 12px 15px; margin-bottom: 8px; transition: border-color .15s;
}
.news-card:hover {border-color: #374250;}
.news-card a {
    color: #cfd8e3; text-decoration: none; font-weight: 500;
    font-size: 0.95rem; line-height: 1.45;
}
.news-card a:hover {color: #93b5d6;}
.news-meta {color: #7d8793; font-size: 0.76rem; margin-top: 5px;}

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
# DAFTAR SAHAM (kode IDX tanpa .JK)
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
    "DEWA": "Darma Henwa",
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
# SUMBER BERITA (semua gratis)
# ============================================================
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; IDXNewsAI/1.0)"}

# Situs finansial Indonesia yang dicari lewat Google News (operator site:)
NEWS_SITES = ["cnbcindonesia.com", "kontan.co.id", "bisnis.com", "idxchannel.com", "emitennews.com"]
SITES_Q = " OR ".join(f"site:{s}" for s in NEWS_SITES)

# Feed RSS langsung. Kalau salah satu URL mati/berubah, otomatis di-skip
# (cek jumlah per sumber di bawah judul "Berita"). Bebas tambah/ganti.
DIRECT_FEEDS = {
    "CNBC Indonesia": "https://www.cnbcindonesia.com/market/rss",
    "Antara": "https://www.antaranews.com/rss/ekonomi.xml",
    "Detik Finance": "https://rss.detik.com/index.php/finance",
}


def _get(url: str, timeout: int = 8) -> bytes:
    r = requests.get(url, headers=HEADERS, timeout=timeout)
    r.raise_for_status()
    return r.content


def _gnews(query: str):
    url = "https://news.google.com/rss/search?" + urlencode(
        {"q": query, "hl": "id", "gl": "ID", "ceid": "ID:id"}
    )
    return parse_rss(_get(url), "Google News", "Google News")[:30]


def _direct(label: str, url: str):
    return parse_rss(_get(url), label, label)[:40]


def _yahoo(symbol: str):
    news = yf.Ticker(symbol).news or []
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
            "via": "Yahoo Finance",
        })
    return out


ARTICLE_TOP_N = 5      # jumlah artikel teratas yang dibaca isinya
ARTICLE_CHARS = 1500   # dipotong per artikel (hemat token)


def _fail(item, reason):
    return {"title": item["title"], "publisher": item["publisher"], "date": item["date"],
            "url": item["link"], "ok": False, "reason": reason}


def _resolve_links(links):
    """Link redirect Google News -> URL artikel asli (batch). Return {link: url_asli}."""
    out = {l: l for l in links if "news.google.com" not in l}
    g = [l for l in links if "news.google.com" in l]
    if not g:
        return out
    try:
        from googlenewsdecoder import gnewsdecoder
        res = gnewsdecoder(g)  # satu request batch untuk semua link
        if isinstance(res, dict):
            res = [res]
        for l, d in zip(g, res):
            if d.get("success", d.get("status")) and d.get("decoded_url"):
                out[l] = d["decoded_url"]
    except Exception:
        pass
    return out


def _fetch_article(item, url):
    """Ambil & ekstrak teks satu artikel. Paywall/gagal -> ok=False (di-skip)."""
    try:
        import trafilatura
    except ImportError:
        return _fail(item, "trafilatura belum terpasang")
    try:
        r = requests.get(url, headers=HEADERS, timeout=8)
    except Exception:
        return _fail(item, "gagal diakses")
    if r.status_code in (401, 402, 403, 451):
        return _fail(item, f"diblokir/paywall (HTTP {r.status_code})")
    if r.status_code != 200 or len(r.content) > 3_000_000:
        return _fail(item, f"HTTP {r.status_code}")
    try:
        text = trafilatura.extract(r.content, include_comments=False, include_tables=False)
    except Exception:
        text = None
    ok, reason = judge_article(text)
    if not ok:
        return _fail(item, reason)
    return {"title": item["title"], "publisher": item["publisher"], "date": item["date"],
            "url": url, "ok": True, "text": trim_text(text, ARTICLE_CHARS)}


@st.cache_data(ttl=3600, show_spinner=False)
def read_articles(items_key: tuple):
    """items_key = ((title, link, publisher, date), ...) urut ranking. Return hasil per artikel."""
    items = [{"title": t, "link": l, "publisher": p, "date": d} for t, l, p, d in items_key]
    resolved = _resolve_links([i["link"] for i in items])
    results = [None] * len(items)
    with ThreadPoolExecutor(max_workers=5) as ex:
        futs = {}
        for idx, it in enumerate(items):
            url = resolved.get(it["link"])
            if not url:
                results[idx] = _fail(it, "link Google News tidak bisa di-resolve")
            else:
                futs[ex.submit(_fetch_article, it, url)] = idx
        for f in as_completed(futs):
            try:
                results[futs[f]] = f.result()
            except Exception:
                results[futs[f]] = _fail(items[futs[f]], "error")
    return results


@st.cache_data(ttl=600, show_spinner=False)
def collect_news(kind: str, code: str = "", name: str = ""):
    """
    kind = 'market' atau 'stock'.
    Return (berita_unik_urut_terbaru, {sumber: jumlah}, berita_urut_ranking).
    Urutan ranking = hasil Google News (relevansi) -> Yahoo -> feed langsung.
    """
    jobs = []
    if kind == "market":
        jobs.append(lambda: _gnews('IHSG OR "bursa saham" OR "pasar modal" when:7d'))
        jobs.append(lambda: _gnews(f"IHSG ({SITES_Q}) when:7d"))
        jobs.append(lambda: _gnews('ekonomi Indonesia OR rupiah OR "suku bunga" OR "Bank Indonesia" when:7d'))
        jobs.append(lambda: _yahoo(INDEX_TICKER))
        direct_filter = None
    else:
        jobs.append(lambda: _gnews(f'("{name}" OR {code}) saham when:30d'))
        jobs.append(lambda: _gnews(f"{code} ({SITES_Q}) when:30d"))
        jobs.append(lambda: _yahoo(f"{code}.JK"))
        direct_filter = [code, name]
    for label, url in DIRECT_FEEDS.items():
        jobs.append(lambda l=label, u=url: _direct(l, u))

    lists = [[] for _ in jobs]
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(j): i for i, j in enumerate(jobs)}
        for f in as_completed(futs):
            try:
                lists[futs[f]] = f.result()
            except Exception:
                pass  # sumber gagal -> di-skip

    if direct_filter:  # feed umum -> ambil yang menyebut saham ini saja
        lists = [
            filter_by_keywords(l, direct_filter) if l and l[0]["via"] in DIRECT_FEEDS else l
            for l in lists
        ]

    stats = {}
    for l in lists:
        for n in l:
            stats[n["via"]] = stats.get(n["via"], 0) + 1
    return merge_news(*lists), stats, merge_ranked(*lists)


@st.cache_data(ttl=600, show_spinner=False)
def get_history(symbol: str, period: str = "1y"):
    try:
        h = yf.Ticker(symbol).history(period=period)
        return h if not h.empty else None
    except Exception:
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_fundamentals(symbol: str):
    try:
        info = yf.Ticker(symbol).info or {}
    except Exception:
        return ""
    parts = []
    if info.get("sector"):
        parts.append(f"sektor {info['sector']}" + (f" / {info['industry']}" if info.get("industry") else ""))
    if info.get("marketCap"):
        parts.append(f"market cap ≈ Rp {info['marketCap'] / 1e12:,.2f} T")
    if info.get("trailingPE"):
        parts.append(f"PER {info['trailingPE']:.1f}")
    if info.get("priceToBook"):
        parts.append(f"PBV {info['priceToBook']:.2f}")
    if info.get("returnOnEquity"):
        parts.append(f"ROE {info['returnOnEquity'] * 100:.1f}%")
    return ("[FUNDAMENTAL RINGKAS] " + ", ".join(parts)) if parts else ""


@st.cache_data(ttl=3600, show_spinner=False)
def search_other_stocks(query: str, max_results: int = 12):
    if not query or len(query.strip()) < 2:
        return []
    found = []
    try:
        resp = requests.get(
            "https://query2.finance.yahoo.com/v1/finance/search",
            params={"q": query, "quotesCount": max_results * 2, "newsCount": 0},
            headers=HEADERS, timeout=6,
        )
        for q in resp.json().get("quotes", []):
            sym = q.get("symbol", "")
            if sym.endswith(".JK"):
                found.append((sym.replace(".JK", ""), q.get("shortname") or q.get("longname") or sym))
    except Exception:
        pass
    return found[:max_results]


# ============================================================
# LLM — Gemini via REST
# ============================================================
GEMINI_MODELS = ["gemini-3.8-flash", "gemini-3.6-flash", "gemini-flash-latest"]


def get_secret(name: str, default: str = "") -> str:
    try:
        return str(st.secrets.get(name, default) or default).strip()
    except Exception:
        return os.environ.get(name, default).strip()


def call_llm(contents, system: str = None, max_tokens: int = 4096):
    """contents: str atau list [{role, parts}]. Return (ok, teks_atau_error)."""
    api_key = get_secret("GEMINI_API_KEY")
    if not api_key:
        return False, "GEMINI_API_KEY belum kebaca. Cek nama variabelnya di Secrets (harus persis GEMINI_API_KEY)."
    if isinstance(contents, str):
        contents = [{"role": "user", "parts": [{"text": contents}]}]

    payload = {
        "contents": contents,
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": max_tokens},
    }
    if system:
        payload["systemInstruction"] = {"parts": [{"text": system}]}

    custom_model = get_secret("GEMINI_MODEL")
    models = [custom_model] if custom_model else GEMINI_MODELS
    errors = []

    for model in models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        r = None
        for attempt in range(3):  # retry kalau model lagi sibuk (429/500/503)
            try:
                r = requests.post(
                    url,
                    headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
                    json=payload, timeout=90,
                )
            except Exception as e:
                errors.append(f"{model}: gagal konek ({e})")
                r = None
                break
            if r.status_code not in (429, 500, 503) or attempt == 2:
                break
            time.sleep(2 * (attempt + 1))  # tunggu 2 detik, lalu 4 detik
        if r is None:
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
        if r.status_code in (401, 403) or "API key" in msg:
            break

    return False, "\n".join(errors)


# ============================================================
# KONTEKS & CHAT
# ============================================================
SYSTEM_PROMPT = """Kamu analis pasar modal Indonesia (IDX). Jawab dalam bahasa yang dipakai pengguna (default Bahasa Indonesia), lugas.

Aturan:
1. Dasarkan jawaban pada DATA TERKINI yang diberikan (berita multi-sumber + indikator teknikal). Jangan mengarang angka atau berita. Kalau data kurang, sebutkan apa yang kurang.
2. Untuk analisis/opini saham: pisahkan [Sentimen berita] dan [Teknikal], lalu beri kesimpulan bias (bullish / netral / bearish), level support-resistance penting, skenario naik vs turun, dan risiko utama.
3. Untuk isu pasar/IHSG: jelaskan jalur dampaknya (mis. suku bunga → bank, komoditas → energi/tambang, rupiah → importir/eksportir) dan sektor/saham yang paling terpengaruh.
4. Sebut sumber/tanggal berita seperlunya. Kalau sumber saling bertentangan, tandai.
5. Untuk jawaban yang berisi opini saham, tutup dengan SATU baris pengingat singkat bahwa ini analisis informatif, bukan rekomendasi beli/jual.
6. Jika ada blok [ISI ARTIKEL ...], utamakan isinya (bukan cuma judul) untuk menilai sentimen, dan kutip fakta/angka penting dengan menyebut medianya."""

MODE_SHORT = "MODE RINGKAS: maksimal ±90 kata, 3–5 poin bullet, langsung ke inti, tanpa pembuka/penutup panjang."
MODE_FULL = "MODE LENGKAP: jawaban terstruktur dengan sub-judul singkat, ±250–400 kata."


def fmt_date(s: str) -> str:
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).strftime("%d %b %Y, %H:%M")
    except Exception:
        return s or "tanggal n/a"


def news_lines(items, limit):
    return "\n".join(
        f"- [{(n['date'] or '????')[:10]}] {n['title']} ({n['publisher']} via {n['via']})"
        for n in items[:limit]
    )


def article_block(label, ranked, n):
    """Baca n artikel teratas (urut ranking). Paywall/gagal di-skip, tanpa cari pengganti."""
    cand = ranked[:n]
    if not cand:
        return "", 0, 0
    res = read_articles(tuple((c["title"], c["link"], c["publisher"], c["date"]) for c in cand))
    oks = [r for r in res if r["ok"]]
    skipped = len(res) - len(oks)
    if not oks:
        return "", 0, skipped
    body = "\n\n".join(
        f"### {r['title']} ({r['publisher']}, {(r['date'] or '????')[:10]})\n{r['text']}" for r in oks
    )
    head = f"[ISI ARTIKEL TERATAS {label} - terbaca {len(oks)} dari {len(res)}, sisanya paywall/gagal & dilewati]"
    return f"{head}\n{body}", len(oks), skipped


def build_context(question: str, scope: str, selected: str, names: dict, read_full: bool = False):
    """Kumpulkan berita + teknikal (+ isi artikel teratas) yang relevan dengan pertanyaan."""
    tickers = detect_tickers(question, STOCKS)
    if scope == "stock" and selected:
        tickers = [selected] + [t for t in tickers if t != selected]
    tickers = tickers[:3]

    parts, used = [], []
    art_ok = art_skip = 0
    mk_items, mk_stats, mk_rank = collect_news("market")
    all_stats = dict(mk_stats)

    mk_limit = 30 if (scope == "market" and not tickers) else 10
    parts.append(f"[BERITA PASAR & EKONOMI INDONESIA - {len(mk_items)} berita unik]\n{news_lines(mk_items, mk_limit)}")

    if scope == "market" or not tickers:
        parts.append(technicals_text("IHSG", compute_technicals(get_history(INDEX_TICKER))))

    per = max(2, ARTICLE_TOP_N // max(1, len(tickers)))  # 5 artikel, dibagi rata kalau banyak saham
    arts = []
    if read_full and not tickers:
        txt, ok_n, skip_n = article_block("PASAR", mk_rank, ARTICLE_TOP_N)
        arts.append(txt)
        art_ok += ok_n
        art_skip += skip_n

    for code in tickers:
        symbol = f"{code}.JK"
        hist = get_history(symbol)
        if hist is None:
            parts.append(f"[{code}] Tidak ditemukan di Yahoo Finance (kode mungkin salah) - abaikan.")
            continue
        name = names.get(code) or STOCKS.get(code) or code
        items, stats, rank = collect_news("stock", code, name)
        for k, v in stats.items():
            all_stats[k] = all_stats.get(k, 0) + v
        fund = get_fundamentals(symbol)
        parts.append(
            f"[BERITA {code} - {name} - {len(items)} berita unik]\n"
            + (news_lines(items, 25) or "(tidak ada berita ditemukan)")
            + "\n" + technicals_text(symbol, compute_technicals(hist))
            + (("\n" + fund) if fund else "")
        )
        used.append(code)
        if read_full:
            txt, ok_n, skip_n = article_block(code, rank, per)
            arts.append(txt)
            art_ok += ok_n
            art_skip += skip_n

    parts.extend(a for a in arts if a)

    src = ", ".join(f"{k} {v}" for k, v in sorted(all_stats.items(), key=lambda x: -x[1]))
    meta = f"Dasar jawaban: {src or 'tanpa berita'}" + (f" + teknikal {', '.join(used)}" if used else " + teknikal IHSG")
    if read_full:
        meta += f" · isi artikel terbaca {art_ok} dari {art_ok + art_skip} (sisanya paywall/gagal, dilewati)"
    return "\n\n".join(parts)[:26000], meta


def ask_ai(question, history, scope, selected, names, concise, read_full=False):
    ctx, meta = build_context(question, scope, selected, names, read_full)
    now = datetime.now().strftime("%d %b %Y %H:%M")
    final = (
        f"DATA TERKINI (diambil {now}):\n{ctx}\n\n"
        f"PERTANYAAN: {question}\n\n{MODE_SHORT if concise else MODE_FULL}"
    )
    contents = [
        {"role": "user" if m["role"] == "user" else "model", "parts": [{"text": m["content"]}]}
        for m in history[-6:]
    ]
    contents.append({"role": "user", "parts": [{"text": final}]})
    ok, text = call_llm(contents, system=SYSTEM_PROMPT)
    return ok, text, meta


def render_chat(key: str, scope: str, selected: str = "", names: dict = None, placeholder: str = ""):
    names = names or STOCKS
    hist_key = f"chat_{key}"
    st.session_state.setdefault(hist_key, [])
    history = st.session_state[hist_key]

    c1, c2, c3, _ = st.columns([1.2, 1.7, 1, 1.1])
    concise = c1.toggle("Ringkas jawaban", key=f"concise_{key}",
                        help="Aktif: jawaban singkat (±90 kata, poin-poin). Mati: jawaban lengkap.")
    read_full = c2.toggle("Baca isi artikel (top 5)", key=f"read_{key}",
                          help="Aktif: isi 5 artikel teratas dibaca (paywall dilewati). Lebih akurat, tapi lebih lambat & boros token.")
    if c3.button("Hapus riwayat", key=f"clr_{key}"):
        history.clear()

    box = st.container()
    q = st.chat_input(placeholder, key=f"in_{key}")

    with box:
        if not history and not q:
            st.markdown(f'<div class="subtle">{placeholder}</div>', unsafe_allow_html=True)
        for m in history:
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m.get("meta"):
                    st.caption(m["meta"])
        if q:
            with st.chat_message("user"):
                st.markdown(q)
            with st.chat_message("assistant"):
                msg = "Membaca artikel teratas, lalu menganalisis..." if read_full else "Mengumpulkan berita & indikator, lalu menganalisis..."
                with st.spinner(msg):
                    ok, text, meta = ask_ai(q, history, scope, selected, names, concise, read_full)
                if ok:
                    st.markdown(text)
                    st.caption(meta)
                else:
                    st.error("LLM gagal dipanggil. Detail error:")
                    st.code(text)
            if ok:
                history.append({"role": "user", "content": q})
                history.append({"role": "assistant", "content": text, "meta": meta})


# ============================================================
# KOMPONEN UI
# ============================================================
def render_news(items, stats, show=8):
    src = " · ".join(f"{k} {v}" for k, v in sorted(stats.items(), key=lambda x: -x[1]) if v)
    st.caption(f"{len(items)} berita unik · {src or 'tidak ada sumber yang merespons'}")
    if not items:
        st.markdown('<div class="subtle">Belum ada berita ditemukan.</div>', unsafe_allow_html=True)
        return

    def card(n):
        return (
            f'<div class="news-card"><a href="{html.escape(n["link"])}" target="_blank">{html.escape(n["title"])}</a>'
            f'<div class="news-meta">{html.escape(n["publisher"])} · {html.escape(fmt_date(n["date"]))}'
            f' · via {html.escape(n["via"])}</div></div>'
        )

    st.markdown("".join(card(n) for n in items[:show]), unsafe_allow_html=True)
    if len(items) > show:
        with st.expander(f"Lihat {len(items) - show} berita lainnya"):
            st.markdown("".join(card(n) for n in items[show:60]), unsafe_allow_html=True)


def render_price(symbol: str):
    hist = get_history(symbol)
    if hist is None or len(hist) < 2:
        st.markdown('<div class="subtle">Data harga tidak tersedia.</div>', unsafe_allow_html=True)
        return
    last, prev = hist["Close"].iloc[-1], hist["Close"].iloc[-2]
    chg = (last - prev) / prev * 100 if prev else 0
    cls = "chg-up" if chg > 0 else "chg-down" if chg < 0 else "chg-flat"
    arrow = "▲" if chg > 0 else "▼" if chg < 0 else "–"
    st.markdown(
        f'<div class="price-big">{last:,.0f}</div>'
        f'<div class="{cls}">{arrow} {chg:+.2f}% dari penutupan sebelumnya</div>',
        unsafe_allow_html=True,
    )
    st.line_chart(hist["Close"].tail(90), height=200, color="#6f8fb0")


# ============================================================
# SIDEBAR
# ============================================================
with st.sidebar:
    st.markdown("### IDX News AI")
    st.markdown('<div class="subtle">Berita multi-sumber + teknikal + analisis AI.</div>', unsafe_allow_html=True)
    st.divider()

    st.markdown("**Pilih saham**")
    code = st.selectbox(
        "Kode saham", STOCK_OPTIONS, index=STOCK_OPTIONS.index("BBCA"),
        format_func=lambda c: f"{c} · {STOCKS[c]}",
        label_visibility="collapsed", help="Klik lalu ketik kode atau nama untuk mencari.",
    )
    names = dict(STOCKS)

    with st.expander("Saham tidak ada di daftar?"):
        q_search = st.text_input("Cari nama / kode", placeholder="contoh: sampoerna, MDKA")
        hits = search_other_stocks(q_search) if q_search else []
        if q_search and not hits:
            st.caption("Tidak ketemu di Yahoo Finance.")
        if hits:
            for c, n in hits:
                names[c] = n
            code = st.radio("Hasil", [c for c, _ in hits],
                            format_func=lambda c: f"{c} · {names[c]}", label_visibility="collapsed")

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
tab_market, tab_stock = st.tabs(["Pasar (IHSG)", "Saham"])

with tab_market:
    st.markdown("## IHSG & Pasar Indonesia")
    st.markdown('<div class="subtle">Tanya isu apa saja: kebijakan, rupiah, suku bunga, sektor, atau minta analisis saham tertentu.</div>',
                unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        render_price(INDEX_TICKER)
    with right:
        st.markdown("**Berita terbaru**")
        mk_items, mk_stats, _ = collect_news("market")
        render_news(mk_items, mk_stats)

    st.divider()
    st.markdown("#### Tanya AI")
    render_chat(
        "market", scope="market", names=names,
        placeholder="Contoh: Apa dampak isu terbaru ke IHSG? / Analisis teknikal dan sentimen saham DEWA",
    )

with tab_stock:
    symbol = f"{code}.JK"
    st.markdown(f"## {code}")
    st.markdown(f'<div class="subtle">{html.escape(names.get(code, code))} · IDX</div>', unsafe_allow_html=True)
    st.write("")
    left, right = st.columns([1, 1.3], gap="large")
    with left:
        render_price(symbol)
    with right:
        st.markdown("**Berita terbaru**")
        s_items, s_stats, _ = collect_news("stock", code, names.get(code, code))
        render_news(s_items, s_stats)

    st.divider()
    st.markdown(f"#### Tanya AI tentang {code}")
    render_chat(
        f"stock_{code}", scope="stock", selected=code, names=names,
        placeholder=f"Contoh: Analisis teknikal dan sentimen {code} / Apa risiko utamanya? / Bandingkan dengan BBRI",
    )

st.write("")
st.markdown(
    f'<div class="subtle">Data: Yahoo Finance, Google News, feed media Indonesia · cache 10 menit · {datetime.now().strftime("%H:%M:%S")}</div>',
    unsafe_allow_html=True,
)
