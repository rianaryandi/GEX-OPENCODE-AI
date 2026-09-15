#!/bin/bash
# Entrypoint Railway: tulis auth + config, jalankan opencode serve + bot.
set -e

mkdir -p ~/.local/share/opencode /app/work /app/data /app/data/incoming

# 1) Kredensial Zen: isi OPENCODE_AUTH_JSON dengan ISI file auth.json
#    dari komputermu (~/.local/share/opencode/auth.json setelah `opencode auth login`)
if [ -n "$OPENCODE_AUTH_JSON" ]; then
  echo "$OPENCODE_AUTH_JSON" > ~/.local/share/opencode/auth.json
else
  echo "[entrypoint] WARNING: OPENCODE_AUTH_JSON kosong, OpenCode akan gagal auth."
fi

# 1b) Validasi + normalisasi auth.json. Auth.json yang cacat (paste kepotong /
#     terbungkus kutip) bikin serve 500 misterius — gagalkan start dgn pesan jelas.
python3 - ~/.local/share/opencode/auth.json <<'PYEOF'
import json, sys
p = sys.argv[1]
try:
    raw = open(p).read()
except FileNotFoundError:
    print("[entrypoint] auth.json TIDAK ADA — isi OPENCODE_AUTH_JSON dulu.")
    sys.exit(3)
# Buang karakter tak terlihat yg sering ikut ke-copy (BOM, zero-width, LRM/RLM)
# di awal/akhir value — ini penyebab "char 0" misterius.
raw = raw.lstrip("\ufeff\u200b\u200c\u200d\u200e\u200f\u2060\u00a0 \t\r\n").rstrip(" \t\r\n")
try:
    d = json.loads(raw)
except Exception as e:
    print(f"[entrypoint] auth.json RUSAK ({e}). Paste ulang persis dari hasil `cat ~/.local/share/opencode/auth.json`.")
    sys.exit(3)
if isinstance(d, str):  # kepaste terbungkus kutip, coba parse sekali lagi
    try:
        d = json.loads(d)
    except Exception as e:
        print(f"[entrypoint] auth.json RUSAK ({e}). Paste ulang.")
        sys.exit(3)
if not isinstance(d, dict) or "opencode" not in d:
    print("[entrypoint] auth.json RUSAK (tidak ada kunci 'opencode'). Paste ulang dari hasil `cat`.")
    sys.exit(3)
open(p, "w").write(json.dumps(d))
print(f"[entrypoint] auth.json VALID ({len(json.dumps(d))} byte), provider: {','.join(d.keys())}.")
PYEOF
[ $? -ne 0 ] && echo "[entrypoint] Berhenti karena auth.json bermasalah." && exit 1

# 1b) Normalisasi env kosong (Railway variable yg ada tapi kosong = string kosong,
#     bukan default). Kosongkan sekalian agar default dipakai.
for v in OPENCODE_MODEL OPENCODE_SERVER_USERNAME DATA_DIR; do
  if [ -z "${!v}" ]; then unset "$v"; fi
done

# 2) Config model (bisa diganti via env OPENCODE_MODEL, default vision + wajar)
#    Ditulis di /app/work karena serve berjalan dengan cwd di sana.
MODEL="${OPENCODE_MODEL:-opencode/gpt-5.6-luna}"
cat > /app/work/opencode.json <<EOF
{
  "\$schema": "https://opencode.ai/config.json",
  "model": "$MODEL",
  "small_model": "opencode/gpt-5-nano",
  "share": "disabled"
}
EOF
echo "[entrypoint] model: $MODEL"

# 3) Password HTTP serve (bot memakainya untuk auth ke serve)
export OPENCODE_SERVER_PASSWORD="${OPENCODE_SERVER_PASSWORD:-changeme}"
export OPENCODE_SERVER_USERNAME="${OPENCODE_SERVER_USERNAME:-opencode}"

# 4) Jalankan serve di workdir /app/work (file bot & kerja agen di sana)
#    DEBUG_MODE=1 -> log level DEBUG supaya penyebab 500 kelihatan di Logs
cd /app/work
if [ "${DEBUG_MODE}" = "1" ]; then
  echo "[entrypoint] DEBUG_MODE aktif."
  opencode --log-level DEBUG serve --port 4096 --hostname 127.0.0.1 &
else
  opencode serve --port 4096 --hostname 127.0.0.1 &
fi
SERVE_PID=$!

# 5) Tunggu sehat
for i in $(seq 1 60); do
  if curl -sf -u "$OPENCODE_SERVER_USERNAME:$OPENCODE_SERVER_PASSWORD" \
      http://127.0.0.1:4096/global/health > /dev/null 2>&1; then
    echo "[entrypoint] opencode serve sehat."
    break
  fi
  sleep 2
  if [ "$i" = "60" ]; then
    echo "[entrypoint] serve tidak sehat setelah 120 dtk, keluar."
    kill $SERVE_PID 2>/dev/null || true
    exit 1
  fi
done

# 6) Jalankan bot (proses utama)
cd /app
exec python3 bot.py
