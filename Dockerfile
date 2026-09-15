FROM node:22-bookworm-slim

# python + ffmpeg (ekstrak frame video) + curl (health check)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

# OpenCode CLI (menyediakan `opencode serve`)
RUN npm install -g opencode-ai

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --break-system-packages -r requirements.txt

COPY bot.py entrypoint.sh opencode.json.example ./
COPY AGENTS.md /app/work/AGENTS.md
RUN chmod +x entrypoint.sh && mkdir -p /app/work /app/data

# Bot pakai polling Telegram (tidak butuh port publik), jadi tanpa EXPOSE.
CMD ["./entrypoint.sh"]
