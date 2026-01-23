import os
import time
import asyncio
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from playwright.async_api import async_playwright

load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PRODUCT_ID = os.getenv('PRODUCT_ID')

try:
    CHAT_ID = int(CHAT_ID)
except (ValueError, TypeError):
    print(f"❌ Ошибка: CHAT_ID должен быть числом! Получено: '{CHAT_ID}'")
    exit(1)

async def check_with_playwright():
    async with async_playwright() as p:
        # 🔴 ДОБАВЬ ФЛАГИ ДЛЯ РАБОТЫ В КОНТЕЙНЕРЕ
        browser = await p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        page = await browser.new_page()

        try:
            # 🔴 ИСПРАВЛЕНО: убраны пробелы в URL
            url = f"https://shop.teamspirit.gg/ru/products/{PRODUCT_ID}"
            print(f"🌐 Открываем страницу: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)

            # Закрываем всплывающее окно
            try:
                close_btn = await page.wait_for_selector('button[aria-label="Close"]', timeout=3000)
                await close_btn.click()
                print("✅ Всплывающее окно закрыто")
            except:
                pass

            await page.wait_for_timeout(2000)

            # 🔴 УДАЛЕНА ЗАПИСЬ ФАЙЛОВ (не работает в GitHub Actions)

            # Ищем кнопку
            main_button = await page.query_selector('button.btn-lg')
            if main_button:
                button_text = await main_button.text_content()
                button_text = button_text.strip() if button_text else ""
                print(f"📌 Кнопка: '{button_text}'")

                # Проверяем только по тексту
                not_available_phrases = ["Нет в наличии", "Not available", "Out of stock"]
                if any(phrase in button_text for phrase in not_available_phrases):
                    print("❌ Товар НЕ доступен")
                    return False

                print("✅ Товар ДОСТУПЕН")
                return True
            else:
                print("⚠️ Кнопка не найдена")
                return False

        except Exception as e:
            print(f"⚠️ Ошибка: {e}")
            return False
        finally:
            await browser.close()

async def send_telegram_message(text):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"❌ Telegram ошибка: {e}")
        return False

def check_product_availability():
    return asyncio.run(check_with_playwright())

def send_test_message():
    msg = f"🔄 Тест монитора\nТовар ID: {PRODUCT_ID}\nВремя: {time.strftime('%H:%M:%S')}"
    return asyncio.run(send_telegram_message(msg))

def send_notification():
    msg = (
        f"🎉 **ТОВАР ПОЯВИЛСЯ!**\n"
        f"🆔 ID: {PRODUCT_ID}\n"
        f"🔗 [Ссылка](https://shop.teamspirit.gg/ru/products/{PRODUCT_ID})\n"  # 🔴 ИСПРАВЛЕНО
        f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return asyncio.run(send_telegram_message(msg))

def main():
    print("🚀 МОНИТОРИНГ TEAM SPIRIT")
    print(f"📦 ID: {PRODUCT_ID} | 👤 Чат: {CHAT_ID}")

    if send_test_message():
        print("✅ Telegram работает")
    else:
        print("⚠️ Проблема с Telegram")

    notification_sent = False
    while True:
        print(f"\n{'='*40}")
        available = check_product_availability()
        if available:
            if not notification_sent:
                print("🎯 ТОВАР ДОСТУПЕН! Отправляем уведомление...")
                if send_notification():
                    notification_sent = True
            else:
                print("📦 Товар всё ещё доступен")
        else:
            notification_sent = False
            print("⏳ Товар не доступен")

        print("⏳ Ждём 10 минут...")
        time.sleep(600)

if __name__ == '__main__':
    required = ['TELEGRAM_TOKEN', 'CHAT_ID', 'PRODUCT_ID']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Отсутствуют переменные: {missing}")
        exit(1)

    if PRODUCT_ID != '555':
        print(f"\n⚠️ Мониторится ID={PRODUCT_ID}, а не худи (555)")

    main()
