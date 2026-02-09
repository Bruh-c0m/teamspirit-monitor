# main.py
import os
import time
import asyncio
import sys
import subprocess
from dotenv import load_dotenv
from telegram import Bot
from telegram.error import TelegramError
from playwright.async_api import async_playwright

# Установка Chromium при старте (если отсутствует)
def install_chromium():
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            if not p.chromium.executable_path.exists():
                raise FileNotFoundError()
    except (ImportError, FileNotFoundError):
        print("📦 Устанавливаем Chromium для Playwright...")
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=True)

install_chromium()

# Загрузка переменных
load_dotenv()
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN')
CHAT_ID = os.getenv('CHAT_ID')
PRODUCT_ID = os.getenv('PRODUCT_ID')

# Проверка CHAT_ID
try:
    CHAT_ID = int(CHAT_ID)
except (ValueError, TypeError):
    print("❌ Ошибка: CHAT_ID должен быть числом!")
    exit(1)

async def check_with_playwright():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        try:
            url = f"https://shop.teamspirit.gg/ru/products/{PRODUCT_ID}"
            print(f"🌐 Открываем страницу: {url}")
            await page.goto(url, wait_until='networkidle', timeout=30000)
            await page.wait_for_timeout(3000)

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

async def send_telegram_message(message_text):
    try:
        bot = Bot(token=TELEGRAM_TOKEN)
        await bot.send_message(chat_id=CHAT_ID, text=message_text, parse_mode='Markdown')
        return True
    except Exception as e:
        print(f"❌ Ошибка отправки в Telegram: {e}")
        return False

def check_product_availability():
    return asyncio.run(check_with_playwright())

def send_test_message():
    test_msg = f"🔄 Тест монитора Team Spirit\nТовар ID: {PRODUCT_ID}\nВремя: {time.strftime('%H:%M:%S')}"
    return asyncio.run(send_telegram_message(test_msg))

def send_notification():
    message = (
        f"🎉 **ТОВАР ПОЯВИЛСЯ В НАЛИЧИИ!**\n"
        f"🏆 Team Spirit Hoodie\n"
        f"🆔 ID: {PRODUCT_ID}\n"
        f"🔗 [Перейти к товару](https://shop.teamspirit.gg/ru/products/{PRODUCT_ID})\n"
        f"🕐 {time.strftime('%Y-%m-%d %H:%M:%S')}"
    )
    return asyncio.run(send_telegram_message(message))

def main():
    print("🚀 МОНИТОРИНГ TEAM SPIRIT")
    print("=" * 50)
    print(f"📦 Мониторим товар ID: {PRODUCT_ID}")
    print(f"👤 Отправляем в чат: {CHAT_ID}")

    if PRODUCT_ID != '555':
        print(f"\n⚠️ ВНИМАНИЕ: сейчас мониторится ID={PRODUCT_ID}, а не худи (555)")

    print("\n🔍 Проверяем Telegram соединение...")
    if send_test_message():
        print("✅ Telegram работает корректно!")
    else:
        print("⚠️ Проблема с Telegram, но продолжаем мониторинг...")

    print("\n🎬 НАЧИНАЕМ МОНИТОРИНГ...")
    notification_sent = False
    check_count = 0

    try:
        while True:
            check_count += 1
            print(f"\n{'='*40}")
            print(f"🔍 Проверка #{check_count} - {time.strftime('%Y-%m-%d %H:%M:%S')}")

            is_available = check_product_availability()

            if is_available:
                if not notification_sent:
                    print("\n" + "🎉" * 10)
                    print("🎯 ТОВАР ДОСТУПЕН! ОТПРАВЛЯЕМ УВЕДОМЛЕНИЕ...")
                    print("🎉" * 10)
                    if send_notification():
                        print("✅ Уведомление отправлено!")
                        notification_sent = True
                    else:
                        print("⚠️ Не удалось отправить уведомление")
                else:
                    print("📦 Товар всё ещё доступен")
            else:
                print("\n⏳ Товар не доступен")
                notification_sent = False

            print(f"\n⏳ Следующая проверка через 10 минут...")
            for i in range(10, 0, -1):
                mins = f"{i} мин" if i > 1 else "1 минуту"
                print(f"   Ожидание: {mins:10}", end='\r')
                time.sleep(60)
            print("   Готово к проверке" + " " * 20)

    except KeyboardInterrupt:
        print("\n👋 Мониторинг остановлен")
    except Exception as e:
        print(f"\n💥 Ошибка: {e}")

if __name__ == '__main__':
    required_vars = ['TELEGRAM_TOKEN', 'CHAT_ID', 'PRODUCT_ID']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        print(f"❌ Отсутствуют переменные: {', '.join(missing_vars)}")
        exit(1)

    # Быстрый тест (опционально, можно закомментировать)
    # quick_test() — убран, чтобы не усложнять

    main()
