import asyncio
import io
import logging
import os
import sys
import math  # Математика (вернул из v3.7 на всякий случай)
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from PIL import Image, ImageColor, ImageDraw
from aiohttp import web

# --- КОНФИГУРАЦИЯ LUX (Брендинг Czerkl) ---
TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
PORT = int(os.getenv("PORT", 10000))
DEV_NAME = "Czerkl"  # Твое новое имя в системе

# Проверка, что все ключи на месте
if not TOKEN or not CHANNEL_ID:
    logging.critical("ОШИБКА: Забыты BOT_TOKEN или CHANNEL_ID!")
    sys.exit(1)

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Создаем чистый холст 1024x1024 пикселя
CANVAS_SIZE = 1024
canvas = Image.new('RGB', (CANVAS_SIZE, CANVAS_SIZE), color='white')

# --- ИНЖЕНЕРНЫЕ МОДУЛИ ---

def fix_y(y_user):
    """Меняем систему координат: 0 теперь внизу, а не вверху"""
    return CANVAS_SIZE - 1 - int(y_user)

def get_emoji(color_name):
    """Lux-фишка: превращаем название цвета в красивый квадратик"""
    mapping = {
        "black": "⬛", "white": "⬜", "red": "🟥", "blue": "🟦",
        "yellow": "🟨", "green": "🟩", "orange": "🟧", "purple": "🟪",
        "pink": "🌸", "gray": "🩶", "brown": "🤎"
    }
    return mapping.get(color_name.lower(), "🎨")

def is_valid_color(color_name):
    """Проверяем, существует ли такой цвет в природе (библиотеке PIL)"""
    try:
        ImageColor.getrgb(color_name)
        return True
    except:
        return False

async def send_canvas_photo(message, caption):
    """Функция подготовки и отправки фото пользователю"""
    with io.BytesIO() as out:
        canvas.save(out, format="PNG") # Сохраняем холст в память
        out.seek(0)
        photo = types.BufferedInputFile(out.read(), filename="update.png")
        # Отправляем фото с поддержкой Markdown в подписи
        await message.answer_photo(photo=photo, caption=caption, parse_mode="Markdown")

async def load_last_canvas():
    """Восстановление холста из твоего канала (безопасность данных)"""
    global canvas
    try:
        async for message in bot.get_chat_history(CHANNEL_ID, limit=10):
            if message.document and message.document.file_name == "matrix.png":
                file_info = await bot.get_file(message.document.file_id)
                file_content = await bot.download_file(file_info.file_path)
                canvas = Image.open(file_content).convert('RGB')
                logging.info(f"[{DEV_NAME}] Холст успешно восстановлен из облака.")
                return
    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")

async def backup_to_channel():
    """Отправка копии холста в закрытый канал (тихий бэкап)"""
    try:
        with io.BytesIO() as out:
            canvas.save(out, format="PNG")
            out.seek(0)
            file = types.BufferedInputFile(out.read(), filename="matrix.png")
            await bot.send_document(CHANNEL_ID, file, caption=f"v3.8 Lux Backup | Dev: {DEV_NAME}", disable_notification=True)
    except Exception as e:
        logging.error(f"Ошибка бэкапа: {e}")

# --- ТЕКСТОВЫЕ МОДУЛИ (UX/UI) ---
COMMANDS_TEXT = (
    "✨ **Инструментарий v3.8 Lux:**\n"
    "• `/add цвет x y` — поставить точку\n"
    "• `/line цвет x1 y1 x2 y2` — линия\n"
    "• `/circle цвет x y r` — окружность\n"
    "• `/fill цвет x1 y1 x2 y2` — залить область\n"
    "• `/zoom x y` — детальный просмотр\n"
    "• `/view` — всё полотно целиком"
)

# --- ОБРАБОТЧИКИ (ЛОГИКА БОТА) ---

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    """Приветствие при первом запуске"""
    welcome = (
        f"💎 **UnionPB v3.8 Lux**\n"
        f"Engine by **{DEV_NAME}**\n\n"
        f"Система: Декартовы координаты (0,0 внизу).\n"
    )
    await message.answer(welcome + COMMANDS_TEXT, parse_mode="Markdown")

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    """Быстрая справка по командам"""
    await message.answer(COMMANDS_TEXT, parse_mode="Markdown")

@dp.message(Command("add"))
async def add_handler(message: types.Message):
    """Добавление точек (можно списком)"""
    lines = message.text.split('\n')
    success = 0
    last_color = "🎨"
    for i, line in enumerate(lines):
        parts = line.split()
        if i == 0: parts = parts[1:] # Убираем само слово /add
        if len(parts) != 3: continue
        try:
            color, x, y_raw = parts[0], int(parts[1]), int(parts[2])
            if not is_valid_color(color): continue
            y = fix_y(y_raw)
            if 0 <= x < CANVAS_SIZE and 0 <= y < CANVAS_SIZE:
                canvas.putpixel((x, y), ImageColor.getrgb(color))
                success += 1
                last_color = get_emoji(color)
        except: continue
    
    if success > 0:
        asyncio.create_task(backup_to_channel()) # Делаем бэкап в фоне
        await send_canvas_photo(message, f"📍 {last_color} Нанесено пикселей: {success}")
    else:
        await message.answer("⚠️ Ошибка! Проверь: `цвет x y` (пример: red 500 500)")

@dp.message(Command("line"))
async def line_handler(message: types.Message):
    """Рисование линии"""
    try:
        p = message.text.split()
        color, x1, y1_r, x2, y2_r = p[1], int(p[2]), int(p[3]), int(p[4]), int(p[5])
        if not is_valid_color(color):
            return await message.answer(f"❌ Цвет '{color}' не поддерживается.")
        
        draw = ImageDraw.Draw(canvas)
        draw.line([x1, fix_y(y1_r), x2, fix_y(y2_r)], fill=ImageColor.getrgb(color), width=1)
        asyncio.create_task(backup_to_channel())
        await send_canvas_photo(message, f"📏 Линия {get_emoji(color)} успешно отрисована.")
    except:
        await message.answer("Ошибка! Инфо: `/line цвет x1 y1 x2 y2`")

@dp.message(Command("circle"))
async def circle_handler(message: types.Message):
    """Рисование круга"""
    try:
        p = message.text.split()
        color, cx, cy_r, r = p[1], int(p[2]), int(p[3]), int(p[4])
        if not is_valid_color(color):
            return await message.answer(f"❌ Цвет '{color}' не найден.")
        
        cy = fix_y(cy_r)
        draw = ImageDraw.Draw(canvas)
        draw.ellipse([cx-r, cy-r, cx+r, cy+r], outline=ImageColor.getrgb(color))
        asyncio.create_task(backup_to_channel())
        await send_canvas_photo(message, f"⭕ Окружность {get_emoji(color)} готова.")
    except:
        await message.answer("Ошибка! Инфо: `/circle цвет x y r`")

@dp.message(Command("fill"))
async def fill_handler(message: types.Message):
    """Заливка прямоугольной области"""
    try:
        p = message.text.split()
        color, x1, y1_r, x2, y2_r = p[1], int(p[2]), int(p[3]), int(p[4]), int(p[5])
        if not is_valid_color(color):
            return await message.answer(f"❌ Цвет '{color}' не найден.")
        
        draw = ImageDraw.Draw(canvas)
        # min/max нужны, чтобы заливка работала, даже если перепутать координаты углов
        draw.rectangle([min(x1, x2), min(fix_y(y1_r), fix_y(y2_r)), max(x1, x2), max(fix_y(y1_r), fix_y(y2_r))], fill=ImageColor.getrgb(color))
        asyncio.create_task(backup_to_channel())
        await send_canvas_photo(message, f"🎨 Заливка {get_emoji(color)} завершена.")
    except:
        await message.answer("Ошибка! Инфо: `/fill цвет x1 y1 x2 y2`")

@dp.message(Command("zoom"))
async def zoom_handler(message: types.Message):
    """Детальный просмотр участка холста"""
    try:
        p = message.text.split()
        cx, cy_raw = int(p[1]), int(p[2])
        cy = fix_y(cy_raw)
        
        # Безопасность: не даем зуму выйти за границы 1024x1024
        cx = max(50, min(CANVAS_SIZE - 50, cx))
        cy = max(50, min(CANVAS_SIZE - 50, cy))
        
        box = (cx-50, cy-50, cx+50, cy+50) # Вырезаем квадрат 100x100
        zoomed = canvas.crop(box).resize((500, 500), resample=Image.NEAREST) # Увеличиваем без размытия
        
        with io.BytesIO() as out:
            zoomed.save(out, format="PNG")
            out.seek(0)
            await message.answer_photo(photo=types.BufferedInputFile(out.read(), filename="z.png"), caption=f"🔍 Сектор {p[1]}:{cy_raw}")
    except:
        await message.answer("Используй: `/zoom x y` (например: /zoom 512 512)")

@dp.message(Command("view"))
async def view_handler(message: types.Message):
    """Показать весь холст"""
    await send_canvas_photo(message, f"🖼 **UnionPB v3.8 Lux**\nDesigned by {DEV_NAME}")

# --- МОДУЛЬ ЗАПУСКА (RENDER READY) ---

async def main():
    logging.basicConfig(level=logging.INFO)
    
    # Поднимаем веб-сервер, чтобы Render не отключал бота
    app = web.Application()
    app.router.add_get("/", lambda r: web.Response(text=f"UnionPB Lux Online | Dev: {DEV_NAME}"))
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', PORT).start()
    
    # Сначала пробуем загрузить старый рисунок, потом начинаем слушать команды
    await load_last_canvas()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())