# main.py
import os
import time
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes
from playwright.async_api import async_playwright, Error as PlaywrightError
import httpx

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PRODUCT_ID = os.getenv('PRODUCT_ID')

try:
    CHAT_ID = int(CHAT_ID)
except (ValueError, TypeError):
    print("❌ Ошибка: CHAT_ID должен быть числом!")
    exit(1)

# Глобальные переменные состояния
last_check_time: datetime | None = None
last_check_result: bool | None = None  # True = доступен, False = нет, None = ошибка

async def check_with_playwright():
    """Проверяет наличие товара через Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        try:
            # 🔥 ИСПРАВЛЕНО: убраны лишние пробелы в URL
            url = f"https://shop.teamspirit.gg/ru/products/{PRODUCT_ID}"
            print(f"🌐 Открываем страницу: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)

            main_button = await page.query_selector('button.btn-lg')
            if not main_button:
                print("⚠️ Кнопка 'btn-lg' не найдена")
                return False

            button_text = (await main_button.text_content()).strip()
            is_disabled = await main_button.get_attribute('disabled')
            print(f"📌 Текст кнопки: '{button_text}' | disabled: {is_disabled}")

            # Явное отсутствие
            if any(txt in button_text for txt in ["Нет в наличии", "Not available", "Out of stock"]):
                return False

            # Проверка размеров
            if "Выберите размер" in button_text or "Select size" in button_text:
                sizes_container = (
                    await page.query_selector('div.purchase-card__sizes') or
                    await page.query_selector('div[role="group"]')
                )
                if sizes_container:
                    size_buttons = await sizes_container.query_selector_all('button')
                    for button in size_buttons:
                        is_disabled = await button.get_attribute('disabled')
                        has_data_disabled = await button.get_attribute('data-disabled')
                        if not is_disabled and not has_data_disabled:
                            return True
                    return False
                else:
                    return False

            # Обычная доступность
            return not is_disabled

        except Exception as e:
            print(f"⚠️ Ошибка Playwright: {e}")
            return False
        finally:
            await browser.close()

async def safe_check_with_retry(max_retries=3, delay=30):
    """Безопасная проверка с повторами при сетевых ошибках"""
    for attempt in range(1, max_retries + 1):
        try:
            result = await check_with_playwright()
            return result
        except (PlaywrightError, httpx.ConnectError, OSError) as e:
            print(f"⚠️ Сетевая ошибка (попытка {attempt}/{max_retries}): {e}")
            if attempt < max_retries:
                await asyncio.sleep(delay)
            else:
                print("   ❌ Все попытки исчерпаны.")
                return None
        except Exception as e:
            print(f"💥 Неожиданная ошибка: {e}")
            return False
    return None

async def send_notification(context: ContextTypes.DEFAULT_TYPE):
    detection_time = last_check_time.strftime('%Y-%m-%d %H:%M:%S') if last_check_time else time.strftime('%Y-%m-%d %H:%M:%S')
    msg = (
        f"🎉 **ТОВАР В НАЛИЧИИ!**\n"
        f"🏆 Team Spirit Hoodie\n"
        f"🆔 ID: {PRODUCT_ID}\n"
        f"🔗 [Ссылка](https://shop.teamspirit.gg/ru/products/{PRODUCT_ID})\n"
        f"🕒 Обнаружено: {detection_time}"
    )
    try:
        await context.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode='Markdown')
        print("✅ Уведомление отправлено!")
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
        return False

# === Команды ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Монитор Team Spirit запущен!")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if last_check_time:
        lc = last_check_time.strftime('%Y-%m-%d %H:%M:%S')
        if last_check_result is True:
            status_text = "✅ Доступен"
        elif last_check_result is False:
            status_text = "❌ Недоступен"
        else:
            status_text = "⚠️ Ошибка при проверке"
        reply = (
            f"📊 **Статус мониторинга**\n"
            f"📦 ID: `{PRODUCT_ID}`\n"
            f"🔍 Последняя проверка: {lc}\n"
            f"📈 Результат: {status_text}\n"
            f"🕗 Сейчас: {now}"
        )
    else:
        reply = "🕗 Мониторинг ещё не начался."

    await update.message.reply_text(reply, parse_mode='Markdown')

# === Фоновая задача ===

async def monitoring_task(context: ContextTypes.DEFAULT_TYPE):
    global last_check_time, last_check_result
    print(f"\n{'='*40}\n🔍 Автоматическая проверка...")

    try:
        available = await safe_check_with_retry(max_retries=3, delay=30)
        last_check_time = datetime.now()
        last_check_result = available

        if available is True:
            print("🎯 ТОВАР ДОСТУПЕН! Отправляем уведомление...")
            await send_notification(context)  # ← Отправляем ВСЕГДА, если доступен
        elif available is False:
            print("⏳ Товар не доступен")
        else:
            print("⚠️ Статус неизвестен (проблема с сетью).")

    except Exception as e:
        print(f"💥 Критическая ошибка в фоновой задаче: {e}")
        last_check_time = datetime.now()
        last_check_result = None

# === Запуск ===

async def post_init(application: Application):
    await application.bot.set_my_commands([
        BotCommand("start", "Запустить бота"),
        BotCommand("status", "Проверить статус"),
    ])
    await application.bot.send_message(
        chat_id=CHAT_ID,
        text=f"🔄 Бот перезапущен\n📦 ID: {PRODUCT_ID}\n🕒 {time.strftime('%Y-%m-%d %H:%M:%S')}",
        parse_mode='Markdown'
    )

def main():
    print("🚀 Запуск Telegram-бота с мониторингом...")
    print(f"📦 ID: {PRODUCT_ID} | 👤 Чат: {CHAT_ID}")

    if PRODUCT_ID != '555':
        print(f"\n⚠️ ВНИМАНИЕ: сейчас мониторится ID={PRODUCT_ID}, а не худи (555)")

    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))

    # Проверка каждые 10 минут (600 сек), как вы хотели изначально
    application.job_queue.run_repeating(monitoring_task, interval=600, first=10)

    print("🤖 Бот запущен. Работает в фоне...")
    application.run_polling(close_loop=False)

if __name__ == '__main__':
    required = ['TELEGRAM_TOKEN', 'CHAT_ID', 'PRODUCT_ID']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Отсутствуют переменные: {missing}")
        exit(1)
    main()
