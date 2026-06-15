"""
╔══════════════════════════════════════╗
║   KAFEL DO'KONI — RENDER PRODUCTION  ║
║   Admin + Mijoz — bitta token        ║
╚══════════════════════════════════════╝
"""
import os
import logging
import asyncio
import html
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiohttp import web

import db

# ══════════════════════════════════════
#   SOZLAMA & XAVFSIZLIK
# ══════════════════════════════════════
# Render Env Variables orqali o'qish, agar bo'lmasa default qiymat
BOT_TOKEN = os.getenv("BOT_TOKEN", "8904101802:AAGrQVi5ZKgyE3wRcD1tWsIgkpIw9WMyjq0")
ADMIN_IDS = [5320183219, 1087021505]

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp      = Dispatcher(storage=storage)

def is_admin(uid): return uid in ADMIN_IDS


# ══════════════════════════════════════
#   CALLBACK DATA & STATES
# ══════════════════════════════════════
class ProductPagination(CallbackData, prefix="prod"):
    size_name: str
    type_name: str
    color_name: str
    page: int

class Reg(StatesGroup):
    first_name = State()
    last_name  = State()
    phone      = State()

class AddKafel(StatesGroup):
    name        = State()
    size        = State()
    type_       = State()
    color       = State()
    price       = State()
    description = State()
    photo       = State()

class Broadcast(StatesGroup):
    text = State()

class ClientFilter(StatesGroup):
    select_size  = State()
    select_type  = State()
    select_color = State()


# ══════════════════════════════════════
#   KLAVIATURALAR (REPLY KEYBOARDS)
# ══════════════════════════════════════
def mijoz_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🏪 Kafellar ro'yxati")],
        [KeyboardButton(text="👤 Mening ma'lumotlarim")],
        [KeyboardButton(text="📞 Bog'lanish")],
    ], resize_keyboard=True)

def admin_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="➕ Kafel qo'shish"),    KeyboardButton(text="📋 Kafellar ro'yxati")],
        [KeyboardButton(text="👥 Foydalanuvchilar"),  KeyboardButton(text="🗑 Kafel o'chirish")],
        [KeyboardButton(text="📊 Statistika"),         KeyboardButton(text="📢 Xabar yuborish")],
        [KeyboardButton(text="👁 Mijoz ko'rinishi")],
    ], resize_keyboard=True)

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)

def phone_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="📱 Raqamni ulashish", request_contact=True)],
        [KeyboardButton(text="❌ Bekor qilish")],
    ], resize_keyboard=True)

def skip_kb():
    return ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="⏭ O'tkazib yuborish")],
        [KeyboardButton(text="❌ Bekor qilish")],
    ], resize_keyboard=True)


# ── DINAMIK TUGMALAR ──
def get_sizes_reply_kb(kafels):
    sizes = sorted(list(set([str(k['size']).strip() for k in kafels if k.get('size')])))
    builder = ReplyKeyboardBuilder()
    for size in sizes:
        builder.button(text=f"📐 {size}")
    builder.adjust(1)
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)

def get_types_reply_kb(kafels, size_name):
    types_list = sorted(list(set([str(k.get('type') or k.get('type_', '')).strip() for k in kafels if str(k['size']).strip() == size_name])))
    builder = ReplyKeyboardBuilder()
    for t in types_list:
        if t and t != "None":
            builder.button(text=f"🧱 {t}")
    builder.adjust(1)
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)

def get_colors_reply_kb(kafels, size_name, type_name):
    colors_list = sorted(list(set([str(k['color']).strip() for k in kafels if str(k['size']).strip() == size_name and str(k.get('type') or k.get('type_', '')).strip() == type_name])))
    builder = ReplyKeyboardBuilder()
    for c in colors_list:
        builder.button(text=f"🎨 {c}")
    builder.adjust(1)
    builder.row(KeyboardButton(text="⬅️ Orqaga"))
    return builder.as_markup(resize_keyboard=True)


# ── MAHSULOT NAZORATI (INLINE) ──
def get_product_control_kb(size_name: str, type_name: str, color_name: str, current_page: int, total_pages: int):
    builder = InlineKeyboardBuilder()
    for p in range(total_pages):
        btn_text = f"[{p + 1}]" if p == current_page else str(p + 1)
        builder.button(
            text=btn_text, 
            callback_data=ProductPagination(size_name=size_name, type_name=type_name, color_name=color_name, page=p).pack()
        )
    builder.adjust(5)
    builder.row(
        types.InlineKeyboardButton(
            text=f"📄 {current_page + 1}/{total_pages} (Tavsif)", 
            callback_data=f"kafel_info:{size_name}:{type_name}:{color_name}:{current_page}"
        )
    )
    return builder.as_markup()


# ══════════════════════════════════════
#   HANDLERS BO'LIMI
# ══════════════════════════════════════
@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    uid = message.from_user.id

    if is_admin(uid):
        await message.answer("👑 <b>Admin Paneli — Kafel Do'koni</b>\n\nQuyidagi amallardan birini tanlang:", parse_mode="HTML", reply_markup=admin_kb())
        return

    if await db.db_is_registered(uid):
        u = await db.db_get_user(uid)
        await message.answer(f"👋 Xush kelibsiz, <b>{html.escape(u['first_name'])} {html.escape(u['last_name'])}</b>!\nBo'limni tanlang:", parse_mode="HTML", reply_markup=mijoz_kb())
    else:
        await message.answer("📝 <b>Ismingizni</b> kiriting:", parse_mode="HTML", reply_markup=cancel_kb())
        await state.set_state(Reg.first_name)

@dp.message(Reg.first_name)
async def reg_ism(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove()); return
    await state.update_data(first_name=message.text.strip())
    await message.answer("📝 <b>Familiyangizni</b> kiriting:", parse_mode="HTML")
    await state.set_state(Reg.last_name)

@dp.message(Reg.last_name)
async def reg_familiya(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove()); return
    await state.update_data(last_name=message.text.strip())
    await message.answer("📱 <b>Telefon raqamingizni</b> ulashing yoki yozing:", parse_mode="HTML", reply_markup=phone_kb())
    await state.set_state(Reg.phone)

@dp.message(Reg.phone, F.contact)
async def reg_contact(message: types.Message, state: FSMContext):
    await _save_user(message, state, message.contact.phone_number)

@dp.message(Reg.phone)
async def reg_phone(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("❌ Bekor qilindi.", reply_markup=ReplyKeyboardRemove()); return
    phone = message.text.strip()
    if not (phone.startswith("+") and len(phone) >= 10): await message.answer("❗ Format noto'g'ri. Masalan: +998901234567"); return
    await _save_user(message, state, phone)

async def _save_user(message: types.Message, state: FSMContext, phone: str):
    data = await state.get_data()
    uid = message.from_user.id
    username = message.from_user.username or "—"
    await db.db_add_user(uid, data["first_name"], data["last_name"], phone, username)
    await state.clear()
    await message.answer(f"🎉 <b>Ro'yxatdan muvaffaqiyatli o'tdingiz!</b>", parse_mode="HTML", reply_markup=mijoz_kb())

@dp.message(F.text == "🏪 Kafellar ro'yxati")
async def client_show_sizes(message: types.Message, state: FSMContext):
    kafels = await db.db_get_kafels()
    if not kafels:
        await message.answer("📭 Hozircha kafellar mavjud emas.")
        return
    await state.set_state(ClientFilter.select_size)
    await message.answer("📐 <b>Kafel o'lchamini tanlang:</b>", parse_mode="HTML", reply_markup=get_sizes_reply_kb(kafels))

@dp.message(ClientFilter.select_size, F.text.startswith("📐 "))
async def client_show_types(message: types.Message, state: FSMContext):
    size = message.text.replace("📐 ", "").strip()
    await state.update_data(chosen_size=size)
    kafels = await db.db_get_kafels()
    kb = get_types_reply_kb(kafels, size)
    await state.set_state(ClientFilter.select_type)
    await message.answer(f"🧱 <b>{size} o'lchamdagi kafel turini tanlang:</b>", parse_mode="HTML", reply_markup=kb)

@dp.message(ClientFilter.select_type, F.text.startswith("🧱 "))
async def client_show_colors(message: types.Message, state: FSMContext):
    type_name = message.text.replace("🧱 ", "").strip()
    await state.update_data(chosen_type=type_name)
    data = await state.get_data()
    kafels = await db.db_get_kafels()
    kb = get_colors_reply_kb(kafels, data['chosen_size'], type_name)
    await state.set_state(ClientFilter.select_color)
    await message.answer(f"🎨 <b>Rangini tanlang:</b>", parse_mode="HTML", reply_markup=kb)

@dp.message(ClientFilter.select_color, F.text.startswith("🎨 "))
async def client_finalize_filter(message: types.Message, state: FSMContext):
    color_name = message.text.replace("🎨 ", "").strip()
    data = await state.get_data()
    size_name = data['chosen_size']
    type_name = data['chosen_type']
    await state.clear()
    await message.answer("🔄 Kafellar yuklanmoqda...", reply_markup=mijoz_kb())
    kafels = await db.db_get_kafels()
    filtered = [
        k for k in kafels if str(k['size']).strip() == size_name 
        and str(k.get('type') or k.get('type_', '')).strip() == type_name
        and str(k['color']).strip() == color_name
    ]
    if not filtered:
        await message.answer("📭 Bunday kafel topilmadi.")
        return
    await send_kafel_page(message, filtered, size_name, type_name, color_name, 0)

@dp.message(ClientFilter.select_size, F.text == "⬅️ Orqaga")
async def back_to_menu(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Asosiy menyu:", reply_markup=mijoz_kb())

@dp.message(ClientFilter.select_type, F.text == "⬅️ Orqaga")
async def back_to_size(message: types.Message, state: FSMContext):
    kafels = await db.db_get_kafels()
    await state.set_state(ClientFilter.select_size)
    await message.answer("📐 <b>Kafel o'lchamini tanlang:</b>", parse_mode="HTML", reply_markup=get_sizes_reply_kb(kafels))

@dp.message(ClientFilter.select_color, F.text == "⬅️ Orqaga")
async def back_to_type(message: types.Message, state: FSMContext):
    data = await state.get_data()
    kafels = await db.db_get_kafels()
    kb = get_types_reply_kb(kafels, data['chosen_size'])
    await state.set_state(ClientFilter.select_type)
    await message.answer(f"🧱 <b>Kafel turini tanlang:</b>", parse_mode="HTML", reply_markup=kb)

@dp.message(F.text == "👤 Mening ma'lumotlarim")
async def my_info(message: types.Message):
    u = await db.db_get_user(message.from_user.id)
    if not u: await message.answer("❗ Ro'yxatdan o'ting: /start"); return
    reg = u['registered_at'].strftime("%d.%m.%Y %H:%M") if u['registered_at'] else "—"
    await message.answer(f"👤 <b>Mening ma'lumotlarim:</b>\n\n📛 Ism: <b>{html.escape(u['first_name'])}</b>\n📛 Familiya: <b>{html.escape(u['last_name'])}</b>\n📱 Telefon: <code>{html.escape(u['phone'])}</code>\n🔖 Username: @{html.escape(u['username'])}\n📅 Ro'yxat: {reg}", parse_mode="HTML")

@dp.message(F.text == "📞 Bog'lanish")
async def contact(message: types.Message):
    await message.answer("📞 <b>Kafel Do'koni — Aloqa</b>\n\n📱 Tel: +998 97 454 50 56\n📍 Manzil: Toshkent sh.\n⏰ Vaqt: 09:00 — 18:00\n📩 Telegram: @admin_username", parse_mode="HTML")


# ══════════════════════════════════════
#   PAGINATION & AUXILIARY FUNCTIONS
# ══════════════════════════════════════
@dp.callback_query(ProductPagination.filter())
async def process_pagination(callback_query: types.CallbackQuery, callback_data: ProductPagination):
    kafels = await db.db_get_kafels()
    filtered = [
        k for k in kafels if str(k['size']).strip() == callback_data.size_name 
        and str(k.get('type') or k.get('type_', '')).strip() == callback_data.type_name
        and str(k['color']).strip() == callback_data.color_name
    ]
    await callback_query.answer()
    try: await callback_query.message.delete()
    except: pass
    await send_kafel_page(callback_query.message, filtered, callback_data.size_name, callback_data.type_name, callback_data.color_name, callback_data.page)

@dp.callback_query(F.data.startswith("kafel_info:"))
async def process_kafel_description(callback_query: types.CallbackQuery):
    _, size, v_type, color, page_str = callback_query.data.split(":")
    page = int(page_str)
    kafels = await db.db_get_kafels()
    filtered = [k for k in kafels if str(k['size']).strip() == size and str(k.get('type') or k.get('type_', '')).strip() == v_type and str(k['color']).strip() == color]
    await callback_query.answer()
    if page < len(filtered):
        k = filtered[page]
        tavsif = k.get('description') or "Ushbu kafel uchun qo'shimcha tavsif kiritilmagan."
        info_text = f"📋 <b>#{k['id']} - Kafel to'liq tavsifi:</b>\n\n{html.escape(str(tavsif))}"
        close_kb = InlineKeyboardBuilder()
        close_kb.button(text="❌ Yopish", callback_data="close_info_msg")
        await callback_query.message.answer(text=info_text, parse_mode="HTML", reply_markup=close_kb.as_markup())

@dp.callback_query(F.data == "close_info_msg")
async def close_info_message(callback_query: types.CallbackQuery):
    await callback_query.answer()
    try: await callback_query.message.delete()
    except: pass

async def send_kafel_page(message: types.Message, kafels_list, size: str, t_name: str, c_name: str, page: int):
    total_pages = len(kafels_list)
    k = kafels_list[page]
    text = (
        f"📦 <b>#{k['id']} Kafel</b>\n\n"
        f"🔹 <b>Nomi:</b> {html.escape(str(k['name']))}\n"
        f"📐 <b>O'lchami:</b> {size}\n"
        f"🧱 <b>Turi:</b> {t_name}\n"
        f"🎨 <b>Rangi:</b> {c_name}\n"
        f"💰 <b>Narxi:</b> {k['price']:,} so'm\n\n"
        f"💡 <i>Batafsil tavsif uchun pastdagi tugmani bosing.</i>"
    )
    kb = get_product_control_kb(size, t_name, c_name, page, total_pages)
    if k.get('photo_id'): await message.answer_photo(photo=k['photo_id'], caption=text, parse_mode="HTML", reply_markup=kb)
    else: await message.answer(text, parse_mode="HTML", reply_markup=kb)


# ══════════════════════════════════════
#   ADMIN SECTIONS (O'z holicha qoldi)
# ══════════════════════════════════════
@dp.message(F.text == "👁 Mijoz ko'rinishi")
async def admin_to_client(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("👁 Mijoz ko'rinishiga o'tdingiz.\nAdmin paneliga qaytish uchun /admin yozing.", reply_markup=mijoz_kb())

@dp.message(F.text == "/admin")
async def back_to_admin(message: types.Message):
    if not is_admin(message.from_user.id): return
    await message.answer("👑 Admin paneliga qaytdingiz.", reply_markup=admin_kb())

@dp.message(F.text == "📊 Statistika")
async def stats(message: types.Message):
    if not is_admin(message.from_user.id): return
    users, kafels = await db.db_count_users(), await db.db_count_kafels()
    await message.answer(f"📊 <b>Statistika:</b>\n\n👥 Foydalanuvchilar: <b>{users} ta</b>\n🏪 Kafellar: <b>{kafels} ta</b>", parse_mode="HTML")

@dp.message(F.text == "📋 Kafellar ro'yxati")
async def list_kafels(message: types.Message):
    if not is_admin(message.from_user.id): return
    kafels = await db.db_get_kafels()
    if not kafels: await message.answer("📭 Hozircha kafellar yo'q."); return
    await message.answer(f"📋 <b>Jami {len(kafels)} ta kafel:</b>", parse_mode="HTML")
    for k in kafels:
        text = f"📦 <b>#{k['id']}</b>\n" + db.kafel_card(k)
        if k['photo_id']: await message.answer_photo(photo=k['photo_id'], caption=text, parse_mode="HTML")
        else: await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "➕ Kafel qo'shish")
async def add_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("➕ <b>Yangi kafel qo'shish</b>\n\n1️⃣ <b>Nomini</b> kiriting:", parse_mode="HTML", reply_markup=cancel_kb())
    await state.set_state(AddKafel.name)

@dp.message(AddKafel.name)
async def add_name(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    await state.update_data(name=message.text.strip())
    await message.answer("2️⃣ <b>O'lchamini</b> kiriting <i>(60x60, 120x120...)</i>:", parse_mode="HTML")
    await state.set_state(AddKafel.size)

@dp.message(AddKafel.size)
async def add_size(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    await state.update_data(size=message.text.strip())
    await message.answer("3️⃣ <b>Turini</b> kiriting <i>(Pol / Devor / Universal / Fasad)</i>:", parse_mode="HTML")
    await state.set_state(AddKafel.type_)

@dp.message(AddKafel.type_)
async def add_type(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    await state.update_data(type_=message.text.strip())
    await message.answer("4️⃣ <b>Rangini</b> kiriting <i>(Oq / Bej / Kulrang...)</i>:", parse_mode="HTML")
    await state.set_state(AddKafel.color)

@dp.message(AddKafel.color)
async def add_color(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    await state.update_data(color=message.text.strip())
    await message.answer("5️⃣ <b>Narxini</b> kiriting (so'mda, faqat raqam):", parse_mode="HTML")
    await state.set_state(AddKafel.price)

@dp.message(AddKafel.price)
async def add_price(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    if not message.text.strip().isdigit(): await message.answer("❗ Faqat raqam:"); return
    await state.update_data(price=int(message.text.strip()))
    await message.answer("6️⃣ <b>Tavsif</b> kiriting:", parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(AddKafel.description)

@dp.message(AddKafel.description)
async def add_desc(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    desc = "" if message.text == "⏭ O'tkazib yuborish" else message.text.strip()
    await state.update_data(description=desc)
    await message.answer("7️⃣ <b>Rasm</b> yuboring:", parse_mode="HTML", reply_markup=skip_kb())
    await state.set_state(AddKafel.photo)

@dp.message(AddKafel.photo, F.photo)
async def add_photo(message: types.Message, state: FSMContext):
    await state.update_data(photo=message.photo[-1].file_id)
    await _finish_add(message, state)

@dp.message(AddKafel.photo)
async def add_skip_photo(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    await state.update_data(photo=None)
    await _finish_add(message, state)

async def _finish_add(message: types.Message, state: FSMContext):
    data = await state.get_data()
    kafel = await db.db_add_kafel(data["name"], data["size"], data["type_"], data["color"], data["price"], data.get("description", ""), data.get("photo"))
    await state.clear()
    await message.answer("✅ <b>Kafel muvaffaqiyatli qo'shildi!</b>\n\n" + db.kafel_card(kafel), parse_mode="HTML", reply_markup=admin_kb())

@dp.message(F.text == "🗑 Kafel o'chirish")
async def delete_start(message: types.Message):
    if not is_admin(message.from_user.id): return
    kafels = await db.db_get_kafels()
    if not kafels: await message.answer("📭 O'chiriladigan kafellar yo'q."); return
    kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=f"🗑 #{k['id']} — {k['name']}")] for k in kafels] + [[KeyboardButton(text="❌ Bekor qilish")]], resize_keyboard=True)
    await message.answer("🗑 Qaysi kafelni o'chirmoqchisiz?", reply_markup=kb)

@dp.message(F.text.startswith("🗑 #"))
async def delete_do(message: types.Message):
    if not is_admin(message.from_user.id): return
    try:
        kid = int(message.text.split("#")[1].split("—")[0].strip())
        ok = await db.db_delete_kafel(kid)
        await message.answer(f"✅ Kafel #{kid} o'chirildi." if ok else "❗ Topilmadi.", reply_markup=admin_kb())
    except: await message.answer("❗ Xato yuz berdi.", reply_markup=admin_kb())

@dp.message(F.text == "👥 Foydalanuvchilar")
async def users_list(message: types.Message):
    if not is_admin(message.from_user.id): return
    users = await db.db_get_all_users()
    if not users: await message.answer("👥 Hozircha foydalanuvchilar yo'q."); return
    text = f"👥 <b>Jami {len(users)} ta foydalanuvchi:</b>\n\n"
    for i, u in enumerate(users, 1):
        reg = u['registered_at'].strftime("%d.%m.%Y") if u['registered_at'] else "—"
        text += f"{i}. 👤 <b>{html.escape(u['first_name'])} {html.escape(u['last_name'])}</b>\n   📱 <code>{html.escape(u['phone'])}</code> | @{html.escape(u['username'])} | {reg}\n\n"
        if len(text) > 3500: await message.answer(text, parse_mode="HTML"); text = ""
    if text: await message.answer(text, parse_mode="HTML")

@dp.message(F.text == "📢 Xabar yuborish")
async def broadcast_start(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.id): return
    await message.answer("📢 Barcha foydalanuvchilarga xabar yozing:", reply_markup=cancel_kb())
    await state.set_state(Broadcast.text)

@dp.message(Broadcast.text)
async def broadcast_do(message: types.Message, state: FSMContext):
    if message.text == "❌ Bekor qilish": await state.clear(); await message.answer("Bekor.", reply_markup=admin_kb()); return
    users = await db.db_get_all_users()
    ok, fail = 0, 0
    for u in users:
        try:
            await bot.send_message(u['telegram_id'], f"📢 <b>Do'kondan xabar:</b>\n\n{html.escape(message.text)}", parse_mode="HTML")
            ok += 1
        except: fail += 1
    await state.clear()
    await message.answer(f"✅ Yuborildi: <b>{ok} ta</b>\n❌ Yetkazilmadi: <b>{fail} ta</b>", parse_mode="HTML", reply_markup=admin_kb())


# ══════════════════════════════════════
#   RENDER WEB SERVER & RUN
# ══════════════════════════════════════
async def handle_hc(request):
    """Render uchun tiriklik signali (Health Check)"""
    return web.Response(text="Bot is perfectly alive!")

async def main():
    await db.init_db()
    print("🚀 Bot Polling rejimida ishga tushdi...")
    
    # Kichik fon serverini sozlaymiz (Render uyquga ketmasligi uchun)
    app = web.Application()
    app.router.add_get("/", handle_hc)
    runner = web.AppRunner(app)
    await runner.setup()
    
    # Render o'zi taqdim etadigan PORT, bo'lmasa 8080 port
    port = int(os.getenv("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Fake Web Server {port}-portda ishga tushdi.")
    
    try:
        await dp.start_polling(bot)
    finally:
        await runner.cleanup()

if __name__ == "__main__":
    asyncio.run(main())