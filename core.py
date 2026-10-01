"""
Logika murni (tanpa streamlit): parsing RSS, merge berita multi-sumber,
indikator teknikal, dan deteksi kode saham dari teks pertanyaan.
"""

import re
import xml.etree.ElementTree as ET
from datetime import timezone
from email.utils import parsedate_to_datetime

# Kata 4 huruf yang sering muncul setelah "saham" tapi bukan kode emiten
STOP_WORDS = {
    "bank", "yang", "dari", "untuk", "ini", "itu", "apa", "naik", "turun", "akan",
    "bisa", "atau", "saya", "kamu", "dong", "nih", "lagi", "mana", "bagus", "jelek",
    "hari", "besok", "kini", "tapi", "dan", "ada", "lain", "baru", "lama", "tren",
}


# ------------------------------------------------------------
# BERITA
# ------------------------------------------------------------
def _iso(pub: str) -> str:
    try:
        dt = parsedate_to_datetime(pub)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        return ""


def parse_rss(xml_bytes, default_source: str, via: str):
    """Parse RSS 2.0 (termasuk Google News) → list berita seragam."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []
    out = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        src_el = it.find("source")
        source = ((src_el.text or "").strip() if src_el is not None else "") or default_source
        suffix = f" - {source}"
        if source and title.endswith(suffix):  # Google News menempel nama media di judul
            title = title[: -len(suffix)].strip()
        out.append({
            "title": title,
            "link": link,
            "publisher": source,
            "date": _iso(it.findtext("pubDate") or ""),
            "via": via,
        })
    return out


def _key(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())[:70]


def merge_news(*lists):
    """Gabung banyak list berita, buang duplikat judul, urut terbaru → lama."""
    seen, merged = set(), []
    for lst in lists:
        for n in lst:
            k = _key(n["title"])
            if k and k not in seen:
                seen.add(k)
                merged.append(n)
    merged.sort(key=lambda n: n["date"], reverse=True)
    return merged


def filter_by_keywords(items, keywords):
    kws = [k for k in keywords if k and len(k) >= 3]
    if not kws:
        return []
    pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in kws) + r")\b", re.I)
    return [n for n in items if pat.search(n["title"])]


# ------------------------------------------------------------
# DETEKSI TICKER
# ------------------------------------------------------------
def detect_tickers(text: str, stocks: dict, limit: int = 3):
    found = []

    def add(c):
        if c not in found:
            found.append(c)

    # 1) token HURUF BESAR yang ada di daftar (BBCA, DEWA, BBCA.JK)
    for m in re.finditer(r"\b([A-Z]{4})(?:\.JK)?\b", text):
        if m.group(1) in stocks:
            add(m.group(1))
    # 2) pola "saham xxxx" / "emiten xxxx" / "kode xxxx" (huruf kecil boleh)
    for m in re.finditer(r"\b(?:saham|emiten|kode)\s+([A-Za-z]{4})\b", text, re.I):
        c = m.group(1).upper()
        if c.lower() not in STOP_WORDS:
            add(c)
    # 3) nama perusahaan disebut lengkap
    low = text.lower()
    for code, name in stocks.items():
        if len(name) >= 5 and name.lower() in low:
            add(code)
    return found[:limit]


# ------------------------------------------------------------
# TEKNIKAL
# ------------------------------------------------------------
def _last(series):
    try:
        v = float(series.iloc[-1])
        return None if v != v else v  # NaN → None
    except Exception:
        return None


def compute_technicals(h):
    """h = DataFrame OHLCV harian (kolom Open/High/Low/Close/Volume)."""
    import pandas as pd

    if h is None or len(h) < 30:
        return None
    close = h["Close"].astype(float)
    high = h["High"].astype(float)
    low = h["Low"].astype(float)
    vol = h["Volume"].astype(float)
    n = len(close)

    def sma(k):
        return _last(close.rolling(k).mean()) if n >= k else None

    def ret(k):
        return (close.iloc[-1] / close.iloc[-1 - k] - 1) * 100 if n > k else None

    # RSI 14 (Wilder)
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    if float(loss.iloc[-1]) == 0:
        rsi = 100.0 if float(gain.iloc[-1]) > 0 else 50.0
    else:
        rsi = _last(100 - 100 / (1 + gain / loss))

    # MACD 12/26/9
    macd = close.ewm(span=12, adjust=False).mean() - close.ewm(span=26, adjust=False).mean()
    sig = macd.ewm(span=9, adjust=False).mean()
    hist = macd - sig
    cross = None
    recent = hist.tail(4)
    if len(recent) >= 2:
        if recent.iloc[-1] > 0 and (recent.iloc[:-1] <= 0).any():
            cross = "bullish crossover (3 bar terakhir)"
        elif recent.iloc[-1] < 0 and (recent.iloc[:-1] >= 0).any():
            cross = "bearish crossover (3 bar terakhir)"

    # Bollinger 20,2
    bb_mid = sma(20)
    bb_std = _last(close.rolling(20).std()) if n >= 20 else None
    bb_up = bb_mid + 2 * bb_std if (bb_mid is not None and bb_std is not None) else None
    bb_lo = bb_mid - 2 * bb_std if (bb_mid is not None and bb_std is not None) else None

    # ATR 14
    prev_close = close.shift(1)
    tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
    atr = _last(tr.ewm(alpha=1 / 14, adjust=False).mean())

    avg_vol20 = float(vol.tail(20).mean())
    price = float(close.iloc[-1])

    return {
        "n": n,
        "price": price,
        "chg_1d": ret(1),
        "r5": ret(5), "r21": ret(21), "r63": ret(63),
        "sma20": sma(20), "sma50": sma(50), "sma200": sma(200),
        "rsi": rsi,
        "macd": _last(macd), "macd_signal": _last(sig), "macd_hist": _last(hist), "macd_cross": cross,
        "bb_up": bb_up, "bb_mid": bb_mid, "bb_lo": bb_lo,
        "atr": atr, "atr_pct": (atr / price * 100) if (atr and price) else None,
        "hi52": float(high.tail(252).max()), "lo52": float(low.tail(252).min()),
        "sup20": float(low.tail(20).min()), "res20": float(high.tail(20).max()),
        "sup60": float(low.tail(60).min()), "res60": float(high.tail(60).max()),
        "vol_ratio": (float(vol.iloc[-1]) / avg_vol20) if avg_vol20 > 0 else None,
    }


def _f(x, d=0, suffix=""):
    return "n/a" if x is None else f"{x:,.{d}f}{suffix}"


def technicals_text(symbol: str, t: dict) -> str:
    if not t:
        return f"{symbol}: data historis tidak cukup untuk indikator teknikal."
    p = t["price"]

    def rel(ma):
        return "n/a" if ma is None else ("di atas" if p > ma else "di bawah")

    rsi = t["rsi"]
    rsi_lbl = "n/a" if rsi is None else ("jenuh beli" if rsi >= 70 else "jenuh jual" if rsi <= 30 else "netral")
    trend = "n/a"
    if t["sma50"] and t["sma200"]:
        trend = "SMA50 di atas SMA200 (golden-cross zone)" if t["sma50"] > t["sma200"] else "SMA50 di bawah SMA200 (death-cross zone)"
    bb_pos = "n/a"
    if t["bb_up"] and t["bb_lo"]:
        bb_pos = "menyentuh/menembus band atas" if p >= t["bb_up"] else "menyentuh/menembus band bawah" if p <= t["bb_lo"] else "di dalam band"

    return "\n".join([
        f"[TEKNIKAL {symbol}] ({t['n']} hari data)",
        f"- Harga terakhir: {_f(p)} | perubahan 1h {_f(t['chg_1d'], 2, '%')}, 5h {_f(t['r5'], 2, '%')}, 1bln {_f(t['r21'], 2, '%')}, 3bln {_f(t['r63'], 2, '%')}",
        f"- SMA20 {_f(t['sma20'])} (harga {rel(t['sma20'])}), SMA50 {_f(t['sma50'])} (harga {rel(t['sma50'])}), SMA200 {_f(t['sma200'])} (harga {rel(t['sma200'])}); {trend}",
        f"- RSI14: {_f(rsi, 1)} ({rsi_lbl})",
        f"- MACD: {_f(t['macd'], 2)} vs signal {_f(t['macd_signal'], 2)}, histogram {_f(t['macd_hist'], 2)}" + (f"; {t['macd_cross']}" if t["macd_cross"] else ""),
        f"- Bollinger(20,2): atas {_f(t['bb_up'])}, tengah {_f(t['bb_mid'])}, bawah {_f(t['bb_lo'])}; harga {bb_pos}",
        f"- ATR14: {_f(t['atr'], 1)} ({_f(t['atr_pct'], 2, '% dari harga')})",
        f"- Support/resistance 20 hari: {_f(t['sup20'])} / {_f(t['res20'])}; 60 hari: {_f(t['sup60'])} / {_f(t['res60'])}",
        f"- 52 minggu: low {_f(t['lo52'])}, high {_f(t['hi52'])}",
        f"- Volume terakhir vs rata-rata 20 hari: {_f(t['vol_ratio'], 2, 'x')}",
    ])


# ------------------------------------------------------------
# ARTIKEL (baca isi berita)
# ------------------------------------------------------------
PAYWALL_HINTS = (
    "berlangganan", "langganan", "subscribe", "subscription", "login untuk", "masuk untuk",
    "khusus pelanggan", "konten premium", "artikel premium", "paywall", "premium content",
    "sign in to read", "register to read", "baca selengkapnya dengan", "member premium",
)


def judge_article(text, min_chars: int = 500):
    """Return (ok, alasan). Artikel terpotong/paywall → ok=False (di-skip)."""
    if not text:
        return False, "tidak ada teks"
    t = text.strip()
    low_tail = t[-400:].lower()
    has_hint = any(h in low_tail for h in PAYWALL_HINTS)
    if len(t) < min_chars:
        return False, "paywall/terpotong" if has_hint or any(h in t.lower() for h in PAYWALL_HINTS) else "teks terlalu pendek"
    if len(t) < 1500 and has_hint:  # teaser + ajakan berlangganan di ujung
        return False, "paywall/terpotong"
    return True, ""


def trim_text(text: str, max_chars: int = 1500) -> str:
    """Potong ke max_chars, usahakan berhenti di akhir kalimat."""
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= max_chars:
        return t
    cut = t[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    return (cut[: end + 1] if end > max_chars * 0.6 else cut).strip()


def merge_ranked(*lists):
    """Gabung list berita, buang duplikat, PERTAHANKAN urutan (ranking sumber)."""
    seen, out = set(), []
    for lst in lists:
        for n in lst:
            k = _key(n["title"])
            if k and k not in seen:
                seen.add(k)
                out.append(n)
    return out
