# Bot Telegram Pribadi → OpenCode (Zen)

Bot hanya menjawab **kamu** (allowlist owner). Hosting di Railway (Dockerfile).
Kemampuan: teks, foto/gambar (vision), dokumen/kode, video (diringkas dari max 6 frame).

## 1) Siapkan di komputermu

```bash
# install opencode lalu login Zen (sekali saja, untuk mengambil auth.json)
curl -fsSL https://opencode.ai/install | bash
opencode auth login
# pilih: OpenCode Zen -> paste API key Zen kamu

# lihat isi kredensialnya (JANGAN disebar, ini rahasia)
cat ~/.local/share/opencode/auth.json
```

Dapatkan juga:
- **Token bot** dari @BotFather di Telegram (`/newbot`)
- **ID Telegram kamu**: chat ke @userinfobot → angka `id`

## 2) Push folder ini ke GitHub

```bash
cd "/storage/emulated/0/__BOT OPENCODE__"
git init && git add . && git commit -m "bot telegram opencode"
# buat repo di github, lalu:
git remote add origin <url-repo> && git push -u origin main
```

## 3) Deploy di Railway

1. Railway → New Project → Deploy from GitHub repo → pilih repo ini.
2. Railway otomatis deteksi **Dockerfile**. Tidak perlu domain publik
   (bot pakai polling, tidak butuh port masuk).
3. (Disarankan) tambah **Volume** dimount ke `/app/data` supaya file
   `incoming/` + mapping sesi tidak hilang tiap redeploy.
4. Isi **Variables**:

| Variable | Isi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | token dari @BotFather |
| `TELEGRAM_OWNER_ID` | ID angka Telegram kamu |
| `OPENCODE_AUTH_JSON` | **seluruh isi** `auth.json` dari langkah 1 (satu baris) |
| `OPENCODE_SERVER_PASSWORD` | password bebas (mis. acak 20 char) |
| `OPENCODE_MODEL` | (opsional) default `opencode/gpt-5.6-luna` |
| `OPENCODE_SERVER_USERNAME` | (opsional) default `opencode` |
| `DATA_DIR` | (opsional) default `/app/data` |

5. Deploy → buka **Logs**, pastikan muncul:
   `[entrypoint] opencode serve sehat.` lalu `bot jalan, model=...`

## 4) Pakai

- `/start`, `/help`, `/new` (sesi baru = lupakan konteks)
- Kirim teks → dijawab dengan memori sesi per chat
- Kirim foto + caption perintah (mis. foto error + "perbaiki")
- Kirim video → diekstrak 6 frame lalu disimpulkan
- Voice note/audio → belum didukung, kirim teks saja

## Ganti model

Isi `OPENCODE_MODEL` dengan format `opencode/<id>` (daftar: `https://opencode.ai/zen/v1/models`).
Syarat: **harus yang bisa vision** kalau mau kirim gambar. Contoh murah:
- `opencode/deepseek-v4-flash-vision-exp` (termurah, $0.14/1M input)
- `opencode/gpt-5.6-luna` (default, seimbang)
- `opencode/gemini-3-flash` (vision bagus)

## Catatan biaya

Bot = tiap pesan = pemakaian token Zen. Karena hanya kamu yang pakai,
aman. Awasi pemakaian di dashboard Zen (bisa set monthly limit).
