
#!/usr/bin/env python3
"""
Telegram Bot — Qwen AI via OpenRouter
"""

from openai import OpenAI
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    filters,
    CommandHandler,
    ContextTypes
)

# ==============  ISI BAGIAN INI  ==============
OPENROUTER_API_KEY = "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"
TELEGRAM_BOT_TOKEN = "8217020684:AAElZycbMOju34cQuFdyH8U6aP5iqs9-juk"
MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
SITE_URL = "https://t.me/gexcode_bot"
SITE_NAME = "XA - GDDO AI"
# ===============================================

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY,
    default_headers={
        "HTTP-Referer": SITE_URL,
        "X-Title": SITE_NAME,
    }
)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya adalah AI Assistant!\n"
        "Silakan tanya apa saja, saya siap membantu! 😊"
    )

async def balas_pesan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.effective_message.text
    await update.message.chat.send_action(action="typing")
    
    try:
        res = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": teks}],
            temperature=0.7,
            max_tokens=1500
        )
        jawaban = res.choices[0].message.content or "Maaf, belum ada jawaban."
        if len(jawaban) > 4000:
            jawaban = jawaban[:4000] + "\n\n...(dipotong karena terlalu panjang)"
        await update.message.reply_text(jawaban)
    except Exception as e:
        print(f"Error: {e}")
        await update.message.reply_text(f"⚠️ Error: {str(e)[:100]}")

def main():
    print("🔄 Sedang menyiapkan bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, balas_pesan))
    print("✅ Bot berjalan! Coba kirim pesan ke bot kamu di Telegram 😊")
    app.run_polling()

if __name__ == "__main__":
    main()
