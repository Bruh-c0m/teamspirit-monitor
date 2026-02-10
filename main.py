# main.py (версия для Railway)
import os
import time
import asyncio
import sys
import subprocess
from dotenv import load_dotenv
from telegram import Bot
from playwright.async_api import async_playwright

# === УСТАНОВКА CHROMIUM ПРИ СТАРТЕ ===
def install_chromium():
    """Устанавливает Chromium, если отсутствует"""
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            path = p.chromium.executable_path
            if not os.path.exists(path):
                raise FileNotFoundError()
    except (ImportError, FileNotFoundError):
        print("📦 Устанавливаем Chromium...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Chromium готов!")

# Запускаем установку ДО всего остального
install_chromium()

# === ЗАГРУЗКА ПЕРЕМЕННЫХ ===
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PRODUCT_ID = os.getenv('PRODUCT_ID') or '555'  # fallback на 555

try:
    CHAT_ID = int(CHAT_ID)
except (ValueError, TypeError):
    print("❌ CHAT_ID должен быть числом!")
    exit(1)

# === ФУНКЦИИ ПРОВЕРКИ ===
async def check_with_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--single-process'
            ]
        )
        page = await browser.new_page()
        try:
            url = f"https://shop.teamspirit.gg/ru/products/{PRODUCT_ID}"
            print(f"🌐 Открываем: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(2000)

            main_button = await page.query_selector('button.btn-lg')
            if not main_button:
                return False

            button_text = (await main_button.text_content()).strip()
            is_disabled = await main_button.get_attribute('disabled')

            # Явное отсутствие
            if any(t in button_text for t in ["Нет в наличии", "Not available", "Out of stock"]):
                return False

            # Проверка размеров
            if "Выберите размер" in button_text or "Select size" in button_text:
                sizes_container = (
                    await page.query_selector('div.purchase-card__sizes') or
                    await page.query_selector('div[role="group"]')
                )
                if sizes_container:
                    buttons = await sizes_container.query_selector_all('button')
                    for btn in buttons:
                        if not await btn.get_attribute('disabled') and not await btn.get_attribute('data-disabled'):
                            return True
                    return False
                return False

            return not is_disabled
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
    msg = f"🔄 Монитор запущен\nID: {PRODUCT_ID}\n🕒 {time.strftime('%H:%M:%S')}"
    return asyncio.run(send_telegram_message(msg))

def send_notification():
    msg = (
        f"🎉 **ТОВАР В НАЛИЧИИ!**\n"
        f"🆔 ID: {PRODUCT_ID}\n"
        f"🔗 [Ссылка](https://shop.teamspirit.gg/ru/products/{PRODUCT_ID})\n"
        f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return asyncio.run(send_telegram_message(msg))

# === ОСНОВНОЙ ЦИКЛ ===
def main():
    print("🚀 МОНИТОРИНГ TEAM SPIRIT")
    print(f"📦 ID: {PRODUCT_ID} | 👤 Чат: {CHAT_ID}")

    if PRODUCT_ID != '555':
        print(f"\n⚠️ ВНИМАНИЕ: мониторится ID={PRODUCT_ID}, а не худи (555)")

    if send_test_message():
        print("✅ Telegram работает")
    else:
        print("⚠️ Проблема с Telegram")

    print("\n🎬 Начинаем мониторинг...")
    notified = False
    check = 0

    while True:
        check += 1
        print(f"\n{'='*40}\n🔍 Проверка #{check} - {time.strftime('%Y-%m-%d %H:%M:%S')}")

        available = check_product_availability()

        if available:
            if not notified:
                print("🎯 ТОВАР ДОСТУПЕН! Отправляем уведомление...")
                if send_notification():
                    print("✅ Уведомление отправлено!")
                    notified = True
            else:
                print("📦 Товар всё ещё доступен")
        else:
            print("⏳ Товар недоступен")
            notified = False

        print("\n⏳ Ждём 10 минут...")
        time.sleep(600)  # 10 минут

if __name__ == '__main__':
    required = ['TELEGRAM_TOKEN', 'CHAT_ID']
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        print(f"❌ Отсутствуют переменные: {', '.join(missing)}")
        exit(1)
    main()
