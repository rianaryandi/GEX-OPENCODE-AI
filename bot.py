"""Bot Telegram pribadi -> OpenCode (Zen) di Railway.

Alur:
  chat devreze -> bot -> opencode serve (HTTP API, 1 sesi per chat) -> jawab balik

Kemampuan:
  - teks -> langsung dijawab (dengan memori sesi per chat)
  - foto/gambar -> diunduh, OpenCode membacanya via vision
  - dokumen (txt/kode/dll) -> OpenCode membacanya dari folder incoming/
  - video -> TIDAK bisa ditonton langsung; bot ekstrak max 6 frame (ffmpeg)
    + OpenCode menyimpulkan dari frame-frame itu
  - voice/audio -> tidak didukung (tanpa layanan transkrip), bot menolak baik-baik

Env yang dibutuhkan:
  TELEGRAM_BOT_TOKEN   token dari @BotFather
  TELEGRAM_OWNER_ID    ID angka Telegram kamu (bot hanya jawab ini)
  OPENCODE_SERVER_PASSWORD  samakan dengan env serve di entrypoint.sh
  OPENCODE_URL         default http://127.0.0.1:4096
  OPENCODE_MODEL       default opencode/gpt-5.6-luna (boleh diganti yg vision)
  DATA_DIR             default /app/data (pasang Volume Railway ke sini)
"""

import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import httpx
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tg-opencode")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OWNER_ID = int(os.environ["TELEGRAM_OWNER_ID"])
OPENCODE_URL = os.environ.get("OPENCODE_URL") or "http://127.0.0.1:4096"
OPENCODE_MODEL = os.environ.get("OPENCODE_MODEL") or "opencode/gpt-5.6-luna"
SERVER_USER = os.environ.get("OPENCODE_SERVER_USERNAME") or "opencode"
SERVER_PASS = os.environ.get("OPENCODE_SERVER_PASSWORD") or "changeme"

DATA_DIR = Path(os.environ.get("DATA_DIR", "/app/data"))
INCOMING = DATA_DIR / "incoming"
SESS_FILE = DATA_DIR / "sessions.json"
INCOMING.mkdir(parents=True, exist_ok=True)

MAX_VIDEO_FRAMES = 6
HTTP_TIMEOUT = 300  # agen bisa lama berpikir


# ---------- sesi per chat ----------

def _load_sessions() -> dict:
    try:
        return json.loads(SESS_FILE.read_text())
    except Exception:
        return {}


def _save_sessions(m: dict) -> None:
    try:
        SESS_FILE.write_text(json.dumps(m))
    except Exception as e:
        log.warning("gagal simpan sessions: %s", e)


def oc(method: str, path: str, payload: dict | None = None) -> dict:
    """Panggil HTTP API opencode serve (blocking; jalankan via to_thread)."""
    with httpx.Client(timeout=HTTP_TIMEOUT) as c:
        r = c.request(
            method, OPENCODE_URL + path, json=payload,
            auth=(SERVER_USER, SERVER_PASS),
        )
        try:
            r.raise_for_status()
        except httpx.HTTPStatusError as e:
            # Sertakan body agar pesan error Telegram menunjukkan penyebab aslinya
            raise RuntimeError(f"{e} | body: {(r.text or '')[:300]}") from None
        return r.json() if r.text else {}


def get_session(chat_id: int) -> str:
    m = _load_sessions()
    sid = m.get(str(chat_id))
    if sid:
        try:
            oc("GET", f"/session/{sid}")
            return sid
        except Exception:
            pass  # sesi basi (serve restart) -> buat baru
    data = oc("POST", "/session", {"title": f"telegram-{chat_id}"})
    sid = data.get("id") or data.get("sessionID")
    m[str(chat_id)] = sid
    _save_sessions(m)
    return sid


def _model_obj() -> dict | None:
    """Ubah 'opencode/gpt-5.6-luna' -> {'providerID': ..., 'modelID': ...}.
    API serve menolak model berbentuk string (400 Bad Request)."""
    spec = (OPENCODE_MODEL or "").strip()
    if not spec or "/" not in spec:
        return None  # pakai model default server (opencode.json)
    provider, _, model = spec.partition("/")
    if not provider or not model:
        return None
    return {"providerID": provider, "modelID": model}


def ask_oc(chat_id: int, text: str) -> str:
    sid = get_session(chat_id)
    payload: dict = {"parts": [{"type": "text", "text": text}]}
    m = _model_obj()
    if m:
        payload["model"] = m
    data = oc("POST", f"/session/{sid}/message", payload)
    texts = [p.get("text", "") for p in data.get("parts", []) if p.get("type") == "text"]
    jawab = "".join(texts).strip()
    return jawab or "(agen tidak mengembalikan teks)"


# ---------- video -> frame ----------

def extract_frames(video: Path, outdir: Path, n: int = MAX_VIDEO_FRAMES) -> list[Path]:
    """Ambil n frame tersebar merata. Butuh ffmpeg+ffprobe di image."""
    outdir.mkdir(parents=True, exist_ok=True)
    dur = 0.0
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
            capture_output=True, text=True, timeout=30,
        )
        dur = float(r.stdout.strip())
    except Exception as e:
        log.warning("ffprobe gagal: %s", e)
    fps = (n / dur) if dur > n else 1.0
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-i", str(video),
         "-vf", f"fps={fps:.4f},scale=768:-1", str(outdir / "f_%02d.jpg")],
        timeout=120, check=True,
    )
    return sorted(outdir.glob("f_*.jpg"))[:n]


# ---------- handler ----------

async def _only_owner(update: Update) -> bool:
    user = update.effective_user
    if not user or user.id != OWNER_ID:
        if update.effective_message:
            await update.effective_message.reply_text("🤖 Bot pribadi, akses ditolak.")
        return False
    return True


async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    await update.message.reply_text(
        "Halo! Saya terhubung ke OpenCode. Kirim teks / foto / file.\n"
        "Video saya ringkas via frame. Perintah: /new = sesi baru, /help = bantuan."
    )


async def cmd_help(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    await update.message.reply_text(
        "/new = mulai sesi baru (lupakan konteks lama)\n"
        "Kirim foto + caption perintah, mis. foto error + 'jelaskan'.\n"
        "Video max diringkas dari 6 frame."
    )


async def cmd_new(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    m = _load_sessions()
    m.pop(str(update.effective_chat.id), None)
    _save_sessions(m)
    await update.message.reply_text("Sesi baru dimulai. Konteks lama dibuang.")


def _reply_chunks(text: str) -> list[str]:
    if len(text) <= 4000:
        return [text]
    out, cur = [], ""
    for line in text.splitlines(keepends=True):
        if len(cur) + len(line) > 4000:
            out.append(cur)
            cur = ""
        cur += line
    if cur:
        out.append(cur)
    return out


async def _jawab(update: Update, prompt: str):
    chat_id = update.effective_chat.id
    placeholder = await update.message.reply_text("⏳ Berpikir...")
    try:
        jawab = await asyncio.to_thread(ask_oc, chat_id, prompt)
    except Exception as e:
        log.exception("opencode error")
        await placeholder.edit_text(f"❌ Gagal hubungi OpenCode: {e}")
        return
    try:
        await placeholder.delete()
    except Exception:
        pass
    for ch in _reply_chunks(jawab):
        await update.message.reply_text(ch)


async def on_text(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    await _jawab(update, update.message.text)


async def on_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    tg_file = await update.message.photo[-1].get_file()
    ts = int(time.time())
    path = INCOMING / f"img_{update.effective_chat.id}_{ts}.jpg"
    await tg_file.download_to_drive(path)
    caption = (update.message.caption or "Jelaskan isi gambar ini.").strip()
    await _jawab(update, f"User mengirim 1 gambar tersimpan di: {path}\n"
                         f"BACA gambar itu dengan tool read, lalu: {caption}")


async def on_doc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    doc = update.message.document
    mime = (doc.mime_type or "")
    ts = int(time.time())
    path = INCOMING / f"doc_{update.effective_chat.id}_{ts}_{doc.file_name or 'file'}"
    tg_file = await doc.get_file()
    await tg_file.download_to_drive(path)
    caption = (update.message.caption or "").strip()
    if mime.startswith("image/"):
        tugas = "BACA gambar itu dengan tool read lalu jelaskan."
    elif mime.startswith("video/"):
        await _jawab(update, f"User mengirim file video: {path}. {await _video_prompt(path, caption)}")
        return
    else:
        tugas = "BACA file itu dengan tool read/grep lalu simpulkan isinya."
    extra = f" Perintah user: {caption}" if caption else ""
    await _jawab(update, f"User mengirim file ({doc.file_name}, {mime}) tersimpan di: {path}\n{tugas}{extra}")


async def _video_prompt(path: Path, caption: str) -> str:
    try:
        frames = await asyncio.to_thread(
            extract_frames, path, path.parent / (path.stem + "_frames"))
    except FileNotFoundError:
        return ("Maaf, ffmpeg tidak tersedia di server sehingga video tidak bisa diproses.")
    except Exception as e:
        log.exception("ffmpeg error")
        return f"Maaf, gagal ekstrak frame video ({e})."
    if not frames:
        return "Maaf, tidak ada frame yang bisa diekstrak dari video itu."
    daftar = "\n".join(f"- {f}" for f in frames)
    per = f" Perintah user: {caption}" if (caption or "").strip() else ""
    return (f"User mengirim VIDEO (disimpan di {path}). OpenCode tidak bisa menonton video "
            f"langsung, jadi saya ekstrak {len(frames)} frame. BACA semua frame berikut "
            f"dengan tool read lalu simpulkan isi video dan tindak lanjuti:{per}\n{daftar}")


async def on_video(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    v = update.message.video or update.message.animation
    tg_file = await v.get_file()
    ts = int(time.time())
    path = INCOMING / f"vid_{update.effective_chat.id}_{ts}.mp4"
    await tg_file.download_to_drive(path)
    caption = (update.message.caption or "").strip()
    await update.message.reply_text("📹 Video diterima, mengekstrak frame...")
    await _jawab(update, await _video_prompt(path, caption))


async def on_audio(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not await _only_owner(update):
        return
    await update.message.reply_text(
        "🎙️ Voice note / audio belum didukung (tanpa layanan transkrip). "
        "Kirim sebagai teks saja ya.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("new", cmd_new))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_handler(MessageHandler(filters.PHOTO, on_photo))
    app.add_handler(MessageHandler(filters.ATTACHMENT & ~filters.PHOTO, on_doc))
    app.add_handler(MessageHandler(filters.VIDEO | filters.ANIMATION, on_video))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_audio))
    log.info("bot jalan, model=%s", OPENCODE_MODEL)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
