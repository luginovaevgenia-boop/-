import logging
import os

from anthropic import AsyncAnthropic
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

MODEL = "claude-sonnet-5-5"
SYSTEM_PROMPT = "Ты дружелюбный помощник. Отвечай кратко и по делу, на языке собеседника."
MAX_HISTORY = 20  # сколько последних сообщений помнить в каждом чате

logging.basicConfig(level=logging.INFO)
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("Привет! Напиши мне что-нибудь. /reset — забыть наш разговор.")


async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    context.chat_data["history"] = []
    await update.message.reply_text("Готово, начнём сначала.")


async def reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    history = context.chat_data.setdefault("history", [])
    history.append({"role": "user", "content": update.message.text})
    del history[:-MAX_HISTORY]
    # история должна начинаться с сообщения пользователя
    while history and history[0]["role"] != "user":
        history.pop(0)

    await context.bot.send_chat_action(update.effective_chat.id, ChatAction.TYPING)
    try:
        response = await client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            messages=history,
        )
        text = "".join(b.text for b in response.content if b.type == "text") or "(пустой ответ)"
    except Exception:
        logging.exception("Ошибка при обращении к Claude")
        history.pop()  # убрать вопрос, на который не получили ответ
        await update.message.reply_text("Что-то пошло не так, попробуй ещё раз.")
        return

    history.append({"role": "assistant", "content": text})
    for i in range(0, len(text), 4000):  # лимит Telegram — 4096 символов
        await update.message.reply_text(text[i : i + 4000])


def main() -> None:
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, reply))
    app.run_polling()


if __name__ == "__main__":
    main()
