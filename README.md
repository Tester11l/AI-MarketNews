# IDX News AI

App buat mantau berita terbaru Indonesia dari Yahoo Finance, plus analisis AI soal
dampaknya ke IHSG dan ke saham-saham tertentu.

## Fitur
- **Tab Berita Umum**: berita seputar IHSG/pasar Indonesia
- **Tab Berita per Saham**: pilih saham dari watchlist (default LQ45-ish) atau input
  ticker manual, lihat harga terakhir + berita + analisis dampak
- Analisis dibuat oleh LLM (default: Google Gemini, gratis tier)

## Cara Jalanin di Lokal

1. Install dependency:
   ```bash
   pip install -r requirements.txt
   ```

2. Bikin API key gratis di Google AI Studio:
   https://aistudio.google.com/apikey

3. Copy `.streamlit/secrets.toml.example` jadi `.streamlit/secrets.toml`,
   isi `GEMINI_API_KEY` dengan key yang lo dapat.

4. Jalankan:
   ```bash
   streamlit run app.py
   ```

## Cara Deploy Gratis (Streamlit Community Cloud)

1. Push folder ini ke repo GitHub (public atau private, terserah).
   **Pastikan `.streamlit/secrets.toml` yang asli TIDAK ikut ke-push**
   (sudah ada di `.gitignore` — lihat di bawah).

2. Buka https://share.streamlit.io, login pakai akun GitHub.

3. Klik "New app", pilih repo ini, branch, dan file utama `app.py`.

4. Di menu "Advanced settings" → "Secrets", paste isi berikut
   (ganti dengan API key asli lo):
   ```toml
   GEMINI_API_KEY = "api-key-lo"
   ```

5. Klik Deploy. Selesai — app lo online gratis di
   `https://nama-app-lo.streamlit.app`

## Ganti ke Watchlist Sendiri

Edit dictionary `DEFAULT_WATCHLIST` di `app.py`:
```python
DEFAULT_WATCHLIST = {
    "KODE.JK": "Nama Perusahaan",
    ...
}
```
Kode saham IDX di Yahoo Finance selalu pakai suffix `.JK`.

## Ganti LLM dari Gemini ke Claude API

Di `app.py`, fungsi `call_llm()` — tinggal comment bagian Gemini,
uncomment bagian Claude yang sudah disiapkan di bawahnya, lalu tambahkan
`ANTHROPIC_API_KEY` di secrets (dan `anthropic` di requirements.txt).

## Catatan Penting

- `yfinance` **tidak resmi** didukung Yahoo — kadang struktur data berita
  mereka berubah. Kalau tiba-tiba berita kosong/error, cek versi terbaru
  `yfinance` atau struktur `ticker.news` (sudah dihandle fallback di kode).
- Berita index umum (`^JKSE`) kadang lebih sedikit dibanding berita per saham
  individual — ini keterbatasan data dari Yahoo Finance sendiri, bukan bug.
- Free tier Gemini API ada limit request per menit/hari — cukup buat
  pemakaian personal/skripsi/demo.
