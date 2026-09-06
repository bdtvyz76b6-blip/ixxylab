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

BOT_TOKEN = os.getenv("BOT_TOKEN")

API_URL = os.getenv(
    "API_URL",
    "http://localhost:8000"
).rstrip("/")


# ============================================================
# BOT
# ============================================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# API
# ============================================================

async def api_get(path):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                API_URL + path,
                timeout=10
            ) as response:

                if response.status != 200:
                    return None

                return await response.json()

    except Exception:
        return None


async def api_delete_device(token, device_id):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.delete(
                f"{API_URL}/api/device/{token}/{device_id}",
                timeout=10
            ) as response:

                return await response.json()

    except Exception:
        return None


# ============================================================
# KEYBOARDS
# ============================================================

def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🔑 Моя подписка",
                    callback_data="subscription"
                )
            ],
            [
                InlineKeyboardButton(
                    text="📱 Устройства",
                    callback_data="devices"
                ),
                InlineKeyboardButton(
                    text="📊 Трафик",
                    callback_data="traffic"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 Серверы",
                    callback_data="servers"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🔄 Обновить",
                    callback_data="refresh"
                )
            ],
        ]
    )


def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back"
                )
            ]
        ]
    )


def devices_keyboard(devices):
    buttons = []

    for device in devices:
        buttons.append([
            InlineKeyboardButton(
                text=f"🗑 Удалить {device['name']}",
                callback_data=f"delete:{device['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(
            text="🔄 Обновить",
            callback_data="devices"
        )
    ])

    buttons.append([
        InlineKeyboardButton(
            text="⬅️ Назад",
            callback_data="back"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# ============================================================
# HELPERS
# ============================================================

def human_bytes(value):
    value = float(value)

    if value < 1024:
        return f"{value:.0f} B"

    if value < 1024 ** 2:
        return f"{value / 1024:.2f} KB"

    if value < 1024 ** 3:
        return f"{value / 1024 ** 2:.2f} MB"

    if value < 1024 ** 4:
        return f"{value / 1024 ** 3:.2f} GB"

    return f"{value / 1024 ** 4:.2f} TB"


def progress_bar(percent, length=12):
    filled = int(
        length * percent / 100
    )

    filled = max(
        0,
        min(length, filled)
    )

    return (
        "█" * filled +
        "░" * (length - filled)
    )


def user_info_text(data):
    traffic = data["traffic"]

    used = traffic["used"]
    limit = traffic["limit"]
    percent = traffic["percent"]

    devices = data["device_count"]
    device_limit = data["device_limit"]

    return (
        "🦅 <b>ixxy VPN LAB</b>\n\n"

        "🟢 <b>Подписка активна</b>\n\n"

        f"📊 <b>Трафик</b>\n"
        f"{human_bytes(used)} / {human_bytes(limit)}\n"
        f"{progress_bar(percent)} {percent:.1f}%\n\n"

        f"📤 Отправлено: "
        f"{human_bytes(traffic['upload'])}\n"

        f"📥 Получено: "
        f"{human_bytes(traffic['download'])}\n\n"

        f"📱 <b>Устройства</b>\n"
        f"{devices} / {device_limit}\n\n"

        f"📅 <b>До:</b> "
        f"{format_date(data['expire'])}"
    )


def format_date(timestamp):
    from datetime import datetime

    try:
        return datetime.fromtimestamp(
            timestamp
        ).strftime("%d.%m.%Y %H:%M")
    except Exception:
        return "—"


# ============================================================
# START
# ============================================================

@dp.message(CommandStart())
async def start(message: Message):

    data = await api_get(
        f"/api/user/{message.from_user.id}"
    )

    # Пользователя ещё нет
    if not data:
        # Создание пользователя через специальный endpoint
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{API_URL}/api/user/create",
                    json={
                        "telegram_id":
                            message.from_user.id
                    },
                    timeout=10
                ) as response:

                    if response.status != 200:
                        await message.answer(
                            "❌ Не удалось создать подписку."
                        )
                        return

            data = await api_get(
                f"/api/user/{message.from_user.id}"
            )

        except Exception:
            await message.answer(
                "❌ Сервер временно недоступен."
            )
            return

    if not data:
        await message.answer(
            "❌ Не удалось получить данные."
        )
        return

    await message.answer(
        user_info_text(data),
        reply_markup=main_keyboard()
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

@dp.callback_query(F.data == "subscription")
async def subscription(callback: CallbackQuery):

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Ошибка сервера",
            show_alert=True
        )
        return

    token = data["token"]

    link = f"{API_URL}/sub/{token}"

    text = (
        "🔑 <b>Твоя подписка ixxy VPN</b>\n\n"

        "Добавь эту ссылку в Happ:\n\n"

        f"<code>{link}</code>\n\n"

        "📱 Лимит устройств: "
        f"{data['device_count']} / "
        f"{data['device_limit']}\n\n"

        "📊 Трафик: "
        f"{human_bytes(data['traffic']['used'])} / "
        f"{human_bytes(data['traffic']['limit'])}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard()
    )

    await callback.answer()


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(F.data == "devices")
async def devices(callback: CallbackQuery):

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Ошибка сервера",
            show_alert=True
        )
        return

    devices = data["devices"]

    if not devices:
        text = (
            "📱 <b>Мои устройства</b>\n\n"
            "Пока нет зарегистрированных устройств.\n\n"
            f"Лимит: 0 / {data['device_limit']}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard()
        )

        await callback.answer()
        return

    text = (
        "📱 <b>Мои устройства</b>\n\n"
        f"Использовано: "
        f"{len(devices)} / "
        f"{data['device_limit']}\n\n"
    )

    for index, device in enumerate(
        devices,
        start=1
    ):
        text += (
            f"<b>{index}. {device['name']}</b>\n"
            f"   ОС: {device['platform']}\n"
            f"   Добавлено: "
            f"{format_date(device['first_seen'])}\n"
            f"   Активность: "
            f"{format_date(device['last_seen'])}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(devices)
    )

    await callback.answer()


# ============================================================
# DELETE DEVICE
# ============================================================

@dp.callback_query(
    F.data.startswith("delete:")
)
async def delete_device(callback: CallbackQuery):

    device_id = callback.data.split(
        "delete:",
        1
    )[1]

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Ошибка сервера",
            show_alert=True
        )
        return

    result = await api_delete_device(
        data["token"],
        device_id
    )

    if not result or not result.get("success"):
        await callback.answer(
            "❌ Не удалось удалить устройство",
            show_alert=True
        )
        return

    await callback.answer(
        "✅ Устройство удалено"
    )

    # Обновляем список
    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    devices = data["devices"]

    if not devices:
        text = (
            "📱 <b>Мои устройства</b>\n\n"
            "Список пуст.\n\n"
            f"Лимит: 0 / "
            f"{data['device_limit']}"
        )

        await callback.message.edit_text(
            text,
            reply_markup=back_keyboard()
        )

        return

    text = (
        "📱 <b>Мои устройства</b>\n\n"
        f"Использовано: "
        f"{len(devices)} / "
        f"{data['device_limit']}\n\n"
    )

    for index, device in enumerate(
        devices,
        start=1
    ):
        text += (
            f"<b>{index}. {device['name']}</b>\n"
            f"   ОС: {device['platform']}\n"
            f"   Добавлено: "
            f"{format_date(device['first_seen'])}\n\n"
        )

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(devices)
    )


# ============================================================
# TRAFFIC
# ============================================================

@dp.callback_query(F.data == "traffic")
async def traffic(callback: CallbackQuery):

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Ошибка сервера",
            show_alert=True
        )
        return

    traffic = data["traffic"]

    text = (
        "📊 <b>Использование трафика</b>\n\n"

        f"{progress_bar(traffic['percent'], 16)}\n"
        f"<b>{traffic['percent']:.1f}%</b>\n\n"

        f"📤 Отправлено: "
        f"{human_bytes(traffic['upload'])}\n"

        f"📥 Получено: "
        f"{human_bytes(traffic['download'])}\n\n"

        f"📦 Использовано: "
        f"{human_bytes(traffic['used'])}\n"

        f"💾 Лимит: "
        f"{human_bytes(traffic['limit'])}"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard()
    )

    await callback.answer()


# ============================================================
# SERVERS
# ============================================================

@dp.callback_query(F.data == "servers")
async def servers(callback: CallbackQuery):

    text = (
        "🌐 <b>Серверы ixxy VPN</b>\n\n"

        "🟢 Finland\n"
        "🟢 Germany\n"
        "🟢 Netherlands\n"
        "🟢 Mobile LTE\n\n"

        "Статус серверов будет подключён "
        "в следующей версии."
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard()
    )

    await callback.answer()


# ============================================================
# REFRESH
# ============================================================

@dp.callback_query(F.data == "refresh")
async def refresh(callback: CallbackQuery):

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Сервер недоступен",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        user_info_text(data),
        reply_markup=main_keyboard()
    )

    await callback.answer(
        "🔄 Обновлено"
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(F.data == "back")
async def back(callback: CallbackQuery):

    data = await api_get(
        f"/api/user/{callback.from_user.id}"
    )

    if not data:
        await callback.answer(
            "❌ Ошибка сервера",
            show_alert=True
        )
        return

    await callback.message.edit_text(
        user_info_text(data),
        reply_markup=main_keyboard()
    )

    await callback.answer()


# ============================================================
# RUN
# ============================================================

async def main():

    print("ixxy VPN LAB bot started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())