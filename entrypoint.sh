#!/bin/bash
# Entrypoint Railway: tulis auth + config, jalankan opencode serve + bot.
set -e

mkdir -p ~/.local/share/opencode /app/work /app/data /app/data/incoming

# 1) Kredensial Zen: isi OPENCODE_AUTH_JSON dengan ISI file auth.json
#    dari komputermu (~/.local/share/opencode/auth.json setelah `opencode auth login`)
if [ -n "$OPENCODE_AUTH_JSON" ]; then
  echo "$OPENCODE_AUTH_JSON" > ~/.local/share/opencode/auth.json
  echo "[entrypoint] auth.json ditulis."
else
  echo "[entrypoint] WARNING: OPENCODE_AUTH_JSON kosong, OpenCode akan gagal auth."
fi

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
cd /app/work
opencode serve --port 4096 --hostname 127.0.0.1 &
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
