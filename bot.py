import os
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ============================================================
# CONFIG
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# URL нашего server.py после деплоя
PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8000",
).rstrip("/")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан. Добавь BOT_TOKEN в Variables."
    )


# ============================================================
# BOT
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# HTTP HELPERS
# ============================================================

async def api_get(path: str):
    url = f"{PUBLIC_URL}{path}"

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:

                text = await response.text()

                if response.status != 200:
                    return None

                try:
                    import json
                    return json.loads(text)
                except Exception:
                    return text

    except Exception:
        return None


async def api_post(path: str, data: dict):
    url = f"{PUBLIC_URL}{path}"

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data) as response:

                text = await response.text()

                if response.status not in (200, 201):
                    return None

                try:
                    import json
                    return json.loads(text)
                except Exception:
                    return text

    except Exception:
        return None


async def api_delete(path: str):
    url = f"{PUBLIC_URL}{path}"

    timeout = aiohttp.ClientTimeout(total=15)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.delete(url) as response:

                text = await response.text()

                if response.status != 200:
                    return None

                try:
                    import json
                    return json.loads(text)
                except Exception:
                    return text

    except Exception:
        return None


# ============================================================
# FORMAT
# ============================================================

def format_bytes(value: int) -> str:
    value = int(value or 0)

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size = float(value)

    for unit in units:
        if size < 1024:
            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} PB"


def progress_bar(used: int, total: int, length: int = 10) -> str:
    if total <= 0:
        return "░" * length

    percent = min(max(used / total, 0), 1)

    filled = int(percent * length)

    return "█" * filled + "░" * (length - filled)


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="👤 Мой VPN",
                    callback_data="profile",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔗 Получить подписку",
                    callback_data="subscription",
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Трафик",
                    callback_data="traffic",
                ),
                InlineKeyboardButton(
                    text="📱 Устройства",
                    callback_data="devices",
                ),
            ],
            [
                InlineKeyboardButton(
                    text="🌍 Серверы",
                    callback_data="servers",
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="refresh",
                )
            ],
        ]
    )


def back_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ]
        ]
    )


def subscription_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📋 Мой профиль",
                    callback_data="profile",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ],
        ]
    )


# ============================================================
# CREATE / GET USER
# ============================================================

async def get_user(telegram_id: int):

    data = await api_get(
        f"/api/user/{telegram_id}"
    )

    return data


async def create_or_get_user(telegram_id: int):

    user = await get_user(telegram_id)

    if user:
        return user

    user = await api_post(
        "/api/user/create",
        {
            "telegram_id": telegram_id
        }
    )

    return user


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start_handler(message: Message):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ Не удалось подключиться к серверу LAB.\n\n"
            "Попробуй ещё раз через несколько секунд."
        )

        return

    text = (
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "Экспериментальный VPN-сервис.\n\n"
        "Здесь можно протестировать:\n"
        "• VLESS-подписку\n"
        "• лимит устройств\n"
        "• отображение трафика\n"
        "• список серверов\n"
        "• интеграцию с Happ\n\n"
        "Выбери действие:"
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# PROFILE
# ============================================================

async def profile_text(telegram_id: int):

    user = await get_user(telegram_id)

    if not user:
        return (
            "❌ Пользователь не найден.\n"
            "Нажми /start."
        )

    expire = user.get("expire", 0)

    from datetime import datetime

    try:
        expire_text = datetime.fromtimestamp(
            expire
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        expire_text = "—"

    traffic_limit = int(
        user.get("traffic_limit", 0)
    )

    upload = int(
        user.get("upload", 0)
    )

    download = int(
        user.get("download", 0)
    )

    used = upload + download

    devices = int(
        user.get("device_limit", 1)
    )

    return (
        "👤 <b>Мой VPN</b>\n\n"
        f"🆔 Telegram ID: <code>{telegram_id}</code>\n\n"
        f"📅 Действует до: <b>{expire_text}</b>\n"
        f"📱 Лимит устройств: <b>{devices}</b>\n\n"
        f"📦 Лимит трафика: <b>{format_bytes(traffic_limit)}</b>\n"
        f"📊 Использовано: <b>{format_bytes(used)}</b>\n\n"
        f"{progress_bar(used, traffic_limit)}\n\n"
        "Для подключения открой раздел «Получить подписку»."
    )


@dp.callback_query(F.data == "profile")
async def profile_callback(callback: CallbackQuery):

    await callback.answer()

    text = await profile_text(
        callback.from_user.id
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

@dp.callback_query(F.data == "subscription")
async def subscription_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:

        await callback.message.edit_text(
            "❌ Не удалось получить данные пользователя.",
            reply_markup=back_keyboard(),
        )

        return

    token = user.get("token")

    if not token:

        await callback.message.edit_text(
            "❌ Токен ещё не создан.",
            reply_markup=back_keyboard(),
        )

        return

    sub_url = f"{PUBLIC_URL}/sub/{token}"

    text = (
        "🔗 <b>Ваша подписка</b>\n\n"
        "Добавь эту ссылку в Happ:\n\n"
        f"<code>{sub_url}</code>\n\n"
        "📱 <b>Как подключить:</b>\n"
        "1. Скопируй ссылку.\n"
        "2. Открой Happ.\n"
        "3. Добавь подписку по URL.\n"
        "4. Обнови список серверов.\n\n"
        "⚠️ Это экспериментальная LAB-подписка."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔗 Открыть подписку",
                    url=sub_url,
                )
            ],
            [
                InlineKeyboardButton(
                    text="📊 Проверить трафик",
                    callback_data="traffic",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# ============================================================
# TRAFFIC
# ============================================================

@dp.callback_query(F.data == "traffic")
async def traffic_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:

        await callback.message.edit_text(
            "❌ Пользователь не найден.",
            reply_markup=back_keyboard(),
        )

        return

    token = user.get("token")

    if not token:

        await callback.message.edit_text(
            "❌ Токен отсутствует.",
            reply_markup=back_keyboard(),
        )

        return

    traffic = await api_get(
        f"/api/traffic/{token}"
    )

    if not traffic:

        await callback.message.edit_text(
            "❌ Не удалось получить статистику.",
            reply_markup=back_keyboard(),
        )

        return

    upload = int(
        traffic.get("upload", 0)
    )

    download = int(
        traffic.get("download", 0)
    )

    total = int(
        traffic.get("total", 0)
    )

    limit = int(
        traffic.get("traffic_limit", 0)
    )

    used = upload + download

    percent = 0

    if limit > 0:
        percent = min(
            100,
            round(used / limit * 100)
        )

    text = (
        "📊 <b>Трафик</b>\n\n"
        f"⬆️ Отправлено: <b>{format_bytes(upload)}</b>\n"
        f"⬇️ Получено: <b>{format_bytes(download)}</b>\n"
        f"📦 Всего: <b>{format_bytes(total)}</b>\n\n"
        f"💾 Лимит: <b>{format_bytes(limit)}</b>\n"
        f"📈 Использовано: <b>{percent}%</b>\n\n"
        f"{progress_bar(used, limit)}\n\n"
        "ℹ️ В текущей LAB-версии реальный трафик "
        "на внешних VLESS-серверах не передаётся "
        "в наш API автоматически."
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="traffic",
                )
            ],
            [
                InlineKeyboardButton(
                    text="◀️ Назад",
                    callback_data="home",
                )
            ],
        ]
    )

    await callback.message.edit_text(
        text,
        reply_markup=keyboard,
        parse_mode="HTML",
    )


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(F.data == "devices")
async def devices_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:

        await callback.message.edit_text(
            "❌ Пользователь не найден.",
            reply_markup=back_keyboard(),
        )

        return

    token = user.get("token")

    if not token:

        await callback.message.edit_text(
            "❌ Токен отсутствует.",
            reply_markup=back_keyboard(),
        )

        return

    data = await api_get(
        f"/api/token/{token}"
    )

    if not data:

        await callback.message.edit_text(
            "❌ Не удалось получить устройства.",
            reply_markup=back_keyboard(),
        )

        return

    devices = data.get(
        "devices",
        []
    )

    device_limit = int(
        data.get(
            "device_limit",
            user.get("device_limit", 1)
        )
    )

    if not devices:

        text = (
            "📱 <b>Устройства</b>\n\n"
            "Зарегистрированных устройств пока нет.\n\n"
            f"Лимит: <b>{device_limit}</b>"
        )

        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard(),
            parse_mode="HTML",
        )

        return

    lines = [
        "📱 <b>Устройства</b>",
        "",
        f"Лимит: <b>{device_limit}</b>",
        f"Зарегистрировано: <b>{len(devices)}</b>",
        "",
    ]

    for index, device in enumerate(
        devices,
        start=1,
    ):

        name = device.get(
            "device_name",
            "Unknown",
        )

        platform = device.get(
            "platform",
            "Unknown",
        )

        active = device.get(
            "active",
            1,
        )

        status = "🟢" if active else "🔴"

        lines.append(
            f"{status} <b>{index}. {name}</b>\n"
            f"   ОС: {platform}"
        )

    text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# SERVERS
# ============================================================

@dp.callback_query(F.data == "servers")
async def servers_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    data = await api_get(
        "/api/servers"
    )

    if not data:

        await callback.message.edit_text(
            "❌ Не удалось получить список серверов.",
            reply_markup=back_keyboard(),
        )

        return

    servers = data.get(
        "servers",
        []
    )

    if not servers:

        await callback.message.edit_text(
            "❌ Серверы отсутствуют.",
            reply_markup=back_keyboard(),
        )

        return

    lines = [
        "🌍 <b>Серверы ixxy VPN LAB</b>",
        "",
    ]

    for server in servers:

        name = server.get(
            "name",
            "Сервер",
        )

        status = server.get(
            "status",
            "configured",
        )

        if status == "online":
            icon = "🟢"
        elif status == "offline":
            icon = "🔴"
        else:
            icon = "⚪"

        lines.append(
            f"{icon} <b>{name}</b>"
        )

    lines.extend(
        [
            "",
            f"Всего серверов: <b>{len(servers)}</b>",
        ]
    )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# HOME
# ============================================================

@dp.callback_query(F.data == "home")
async def home_callback(
    callback: CallbackQuery,
):

    await callback.answer()

    text = (
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "Экспериментальная панель VPN.\n\n"
        "Выбери действие:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# REFRESH
# ============================================================

@dp.callback_query(F.data == "refresh")
async def refresh_callback(
    callback: CallbackQuery,
):

    await callback.answer(
        "Данные обновлены!"
    )

    text = (
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "Данные пользователя обновлены.\n\n"
        "Выбери нужный раздел:"
    )

    await callback.message.edit_text(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# COMMAND /PROFILE
# ============================================================

@dp.message(Command("profile"))
async def profile_command(
    message: Message,
):

    text = await profile_text(
        message.from_user.id
    )

    await message.answer(
        text,
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# COMMAND /SUB
# ============================================================

@dp.message(Command("sub"))
async def sub_command(
    message: Message,
):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ Не удалось получить данные."
        )

        return

    token = user.get("token")

    if not token:

        await message.answer(
            "❌ Токен отсутствует."
        )

        return

    sub_url = f"{PUBLIC_URL}/sub/{token}"

    await message.answer(
        "🔗 <b>Твоя подписка:</b>\n\n"
        f"<code>{sub_url}</code>\n\n"
        "Добавь её в Happ.",
        parse_mode="HTML",
    )


# ============================================================
# COMMAND /TRAFFIC
# ============================================================

@dp.message(Command("traffic"))
async def traffic_command(
    message: Message,
):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    token = user.get("token")

    if not token:

        await message.answer(
            "❌ Токен отсутствует."
        )

        return

    traffic = await api_get(
        f"/api/traffic/{token}"
    )

    if not traffic:

        await message.answer(
            "❌ Не удалось получить статистику."
        )

        return

    upload = int(
        traffic.get("upload", 0)
    )

    download = int(
        traffic.get("download", 0)
    )

    total = int(
        traffic.get("total", 0)
    )

    limit = int(
        traffic.get("traffic_limit", 0)
    )

    await message.answer(
        "📊 <b>Трафик</b>\n\n"
        f"⬆️ Upload: <b>{format_bytes(upload)}</b>\n"
        f"⬇️ Download: <b>{format_bytes(download)}</b>\n"
        f"📦 Всего: <b>{format_bytes(total)}</b>\n"
        f"💾 Лимит: <b>{format_bytes(limit)}</b>",
        parse_mode="HTML",
    )


# ============================================================
# UNKNOWN CALLBACK
# ============================================================

@dp.callback_query()
async def unknown_callback(
    callback: CallbackQuery,
):

    await callback.answer(
        "Эта кнопка больше не используется.",
        show_alert=True,
    )


# ============================================================
# START BOT
# ============================================================

async def main():

    print("====================================")
    print("      ixxy VPN LAB BOT")
    print("====================================")
    print(
        f"PUBLIC_URL: {PUBLIC_URL}"
    )
    print("Bot starting...")

    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    try:
        asyncio.run(
            main()
        )

    except KeyboardInterrupt:

        print(
            "Bot stopped."
        )