import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.storage.memory import MemoryStorage
from pathlib import Path
from aiogram.types import FSInputFile

import gspread
from google.oauth2.service_account import Credentials

import json
import os

from datetime import datetime

scopes = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

creds_info = json.loads(os.getenv("GOOGLE_CREDS_JSON"))

creds = Credentials.from_service_account_info(
    creds_info,
    scopes=scopes
)

client = gspread.authorize(creds)

sheet = client.open("Заявки").sheet1
def find_user_row(user_id):
    try:
        cell = sheet.find(str(user_id))
        return cell.row
    except:
        return None

def get_all_user_ids():
    rows = sheet.get_all_values()
    user_ids = []

    for row in rows[1:]:  # пропускаем заголовок
        try:
            user_ids.append(int(row[4]))  # 5 колонка = user_id
        except:
            continue

    return user_ids

async def send_reminder(user_id):
    await asyncio.sleep(600)  # 10 минут

    row = find_user_row(user_id)
    if not row:
        return

    row_data = sheet.row_values(row)

    course = row_data[2] if len(row_data) > 2 else None
    status = row_data[5] if len(row_data) > 5 else ""

    if course and status == "выбрал курс":
        try:
            await bot.send_message(
                user_id,
                "Ты выбрал курс, но не оставил заявку 👀\n\nХочешь записаться?"
            )
        except:
            pass

TOKEN = "8791835799:AAEHWNk8KWWQgD21xJrs6W_AY8ALr7m6W9Y"
ADMIN_ID = 907769285

bot = Bot(token=TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# =========================
# FSM
# =========================

class Form(StatesGroup):
    name = State()
    exam = State()

# =========================
# КЛАВИАТУРЫ
# =========================

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📖 О курсах")],
            [KeyboardButton(text="📚 Материалы")],
            [KeyboardButton(text="👨‍🏫 Обо мне")],
        ],
        resize_keyboard=True
    )

def courses_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Уроки в записи")],
            [KeyboardButton(text="👥 Групповые занятия")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

def buy_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="✅ Хочу записаться")],
            [KeyboardButton(text="❌ Пока нет")],
        ],
        resize_keyboard=True
    )

def materials_kb():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🎥 Видео")],
            [KeyboardButton(text="📄 PDF")],
            [KeyboardButton(text="⬅️ Назад")]
        ],
        resize_keyboard=True
    )

# =========================
# START + ОНБОРДИНГ
# =========================

@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await message.answer("Привет! Как тебя зовут?")
    await state.set_state(Form.name)

@dp.message(Form.name)
async def get_name(message: Message, state: FSMContext):
    user = message.from_user
    row = find_user_row(user.id)

    if not row:  # ✅ если пользователя ещё нет
        sheet.append_row([
            message.text,                         # Имя
            "",                                   # Экзамен
            "",                                   # Курс
            user.username or "нет",
            str(user.id),
            "новая",                              # статус
            datetime.now().strftime("%Y-%m-%d")   # 👈 ДАТА
])
    else:  # ✅ если уже есть — обновляем имя
        sheet.update_cell(row, 1, message.text)

    await message.answer("К какому экзамену ты готовишься?\n(ЕГЭ / ДТМ / Сертификат)")
    await state.set_state(Form.exam)

@dp.message(Form.exam)
async def get_exam(message: Message, state: FSMContext):
    user_id = message.from_user.id

    # 🔍 ищем строку пользователя
    row = find_user_row(user_id)

    if row:
        sheet.update_cell(row, 2, message.text)  # колонка 2 = Экзамен

    await message.answer(
        "Отлично 👌\n\nВыбери раздел:",
        reply_markup=main_menu()
    )

    await state.set_state(None)  # чтобы кнопки работали

CHANNEL_ID = "@russian_ot_damir"

async def is_subscribed(user_id: int):
    member = await bot.get_chat_member(CHANNEL_ID, user_id)
    return member.status not in ["left", "kicked"]


# =========================
# МАТЕРИАЛЫ
# =========================
@dp.message(F.text == "📚 Материалы")
async def materials(message: Message):
    if not await is_subscribed(message.from_user.id):
        await message.answer(
            "Чтобы получить доступ к материалам, подпишись на канал 👇\n\n"
            f"https://t.me/{CHANNEL_ID.replace('@','')}"
        )
        return

    await message.answer(
        "Выбери формат материалов 👇",
        reply_markup=materials_kb()
    )

# =========================
# PDF МАТЕРИАЛЫ
# =========================

@dp.message(F.text == "📄 PDF")
async def pdf_materials(message: Message):
    files = [
        ("files/tropy.pdf", "📘 Тропы и фигуры речи"),
        ("files/types.pdf", "📘 Типы речи"),
        ("files/nouns.pdf", "📘 Число существительных"),
    ]

    for path, caption in files:
        await message.answer_document(FSInputFile(path), caption=caption)

# =========================
# ВИДЕО + МАТЕРИАЛЫ
# =========================
from aiogram.types import FSInputFile

BASE_DIR = Path(__file__).parent

@dp.message(F.text == "🎥 Видео")
async def video_materials(message: Message):
    await message.answer("🎥 Онлайн-урок:")

    await message.answer("https://youtu.be/F63Z8roR-2g")

    await message.answer("📄 Дополнительные материалы:")

    conspect_path = BASE_DIR / "files" / "conspect.pdf"
    tetrad_path = BASE_DIR / "files" / "tetrad.pdf"

    await message.answer_document(FSInputFile(conspect_path), caption="Конспект")
    await message.answer_document(FSInputFile(tetrad_path), caption="Рабочая тетрадь")

# =========================
# КУРСЫ
# =========================

@dp.message(F.text == "📖 О курсах")
async def courses(message: Message):
    await message.answer("Выбери формат обучения:", reply_markup=courses_menu())

@dp.message(F.text == "🎥 Уроки в записи")
async def recordings(message: Message):
    user_id = message.from_user.id
    row = find_user_row(user_id)

    if row:
        sheet.update_cell(row, 3, "Уроки в записи")  # колонка 3 = Курс
        sheet.update_cell(row, 6, "выбрал курс")

    await message.answer(
        """🎥 Курс в записи

На курсе вы получаете: 
- 12 уроков в записи
- 4 урока с преподавателем
- домашнее задание и обратную связь 

📚Материалы к каждому уроку:
- 16 рабочих тетрадей и 16 конспектов 

📌Все видео-уроки и материалы размещены на платформе Google Classroom (код доступа выдается после оплаты). Все занятия с преподавателем ведутся через платформу Google Meet 

💰 400 000 сум за один блок (месяц)""",
        reply_markup=buy_menu()
    )
    asyncio.create_task(send_reminder(message.from_user.id))

@dp.message(F.text == "👥 Групповые занятия")
async def group(message: Message):
    user_id = message.from_user.id
    row = find_user_row(user_id)

    if row:
        sheet.update_cell(row, 3, "Групповые занятия")
        sheet.update_cell(row, 6, "выбрал курс")

    await message.answer(
        """👥 Групповые занятия

На курсе вы получаете: 
- 16 уроков с преподавателем 
- домашнее задание и обратную связь

📚Материалы к каждому уроку:
- 16 рабочих тетрадей и 16 конспектов 

📌Все занятия проходят онлайн на платформе Google Meet. Все материалы будут опубликованы на платформе Google Classroom (код доступа будет выдан после оплаты). 

💰 700 000 сум за 16 уроков""",
        reply_markup=buy_menu()
    )
    asyncio.create_task(send_reminder(message.from_user.id))
    
# =========================
# ЗАЯВКА
# =========================

@dp.message(F.text == "✅ Хочу записаться")
async def buy(message: Message):
    user = message.from_user
    user_id = user.id

    row = find_user_row(user_id)

    if not row:
        await message.answer("Сначала пройди регистрацию через /start")
        return

    # 📥 получаем всю строку
    row_data = sheet.row_values(row)

    # защита от короткой строки
    name = row_data[0] if len(row_data) > 0 else user.full_name
    exam = row_data[1] if len(row_data) > 1 else "не указан"
    course = row_data[2] if len(row_data) > 2 else None
    username = row_data[3] if len(row_data) > 3 else "нет"

    if not course:
        await message.answer("Пожалуйста, сначала выбери курс 👇", reply_markup=courses_menu())
        return

    text = (
        "🔥 Новая заявка:\n\n"
        f"Имя: {name}\n"
        f"Экзамен: {exam}\n"
        f"Курс: {course}\n\n"
        f"ID: {user.id}\n"
        f"Username: @{username}"
    )

    sheet.update_cell(row, 6, "заявка отправлена")

    await bot.send_message(ADMIN_ID, text)

    await message.answer("Я скоро с тобой свяжусь 🙌", reply_markup=main_menu())

@dp.message(F.text == "❌ Пока нет")
async def no(message: Message):
    await message.answer("Окей 🙂", reply_markup=main_menu())

    

# =========================
# ОБО МНЕ
# =========================

@dp.message(F.text == "👨‍🏫 Обо мне")
async def about(message: Message):
    await message.answer(
        """👋Привет! Меня зовут Дамир, мне 20 лет. Уже 2 года работаю учителем русского языка и литературы.

📌Помогаю ученикам уверенно подготовиться к:
ЕГЭ
ДТМ
Национальный сертификат.

🧑‍🏫Также я студент Самаркандского государственного университета, факультета русской филологии, обучаюсь на основе государственного гранта.

Записывайся на курс! Буду рад тебя видеть в числе своих учеников❤️"""
    )


# =========================
# НАЗАД
# =========================

@dp.message(F.text == "⬅️ Назад")
async def back(message: Message):
    await message.answer("Главное меню:", reply_markup=main_menu())

# =========================
# РАССЫЛКА
# =========================

from aiogram.filters import Command

@dp.message(Command("broadcast"))
async def broadcast(message: Message, bot: Bot):
    if message.from_user.id != ADMIN_ID:
        return

    text = message.text.replace("/broadcast", "").strip()

    if not text:
        await message.answer("Укажи текст после команды.")
        return

    user_ids = get_all_user_ids()

    sent = 0

    for user_id in user_ids:
        try:
            await bot.send_message(user_id, text)
            sent += 1
            await asyncio.sleep(0.05)
        except:
            continue

    await message.answer(f"Рассылка завершена ✅\nОтправлено: {sent}")
    
# =========================
# ЗАПУСК
# =========================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

