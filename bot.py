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
OPENROUTER_API_KEY = "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"      # Ganti dengan API key kamu
TELEGRAM_BOT_TOKEN = "8217020684:AAElZycbMOju34cQuFdyH8U6aP5iqs9-juk" # Ganti dengan token dari @BotFather
MODEL = "Qwen/Qwen2.5-Coder-7B-Instruct"
# ===============================================

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=OPENROUTER_API_KEY
)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Halo! Saya adalah AI Assistant!\n"
        "Silakan tanya apa saja, saya siap membantu! 😊"
    )

async def balas_pesan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    teks = update.effective_message.text
    
    await update.message.chat.send_action(action="typing")
    
    res = client.chat.completions.create(
        model=MODEL,
        messages=[{"role": "user", "content": teks}],
        temperature=0.7,
        max_tokens=1500
    )
    
    jawaban = res.choices[0].message.content
    
    # Potong kalau terlalu panjang
    if len(jawaban) > 4000:
        jawaban = jawaban[:4000] + "\n\n...(dipotong karena terlalu panjang)"
    
    await update.message.reply_text(jawaban)

def main():
    print("🔄 Sedang menyiapkan bot...")
    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, balas_pesan))
    
    print("✅ Bot siap! Coba kirim pesan ke bot kamu di Telegram 😊")
    app.run_polling()

if __name__ == "__main__":
    main()


