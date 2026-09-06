import os
import asyncio
import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ============================================================
# НАСТРОЙКИ
# ============================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "https://ixxylab-1.onrender.com",
).rstrip("/")


if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан")


# ============================================================
# BOT / DISPATCHER
# ============================================================

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ============================================================
# API
# ============================================================

async def api_get(path: str):
    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:

                text = await response.text()

                if response.status != 200:
                    print(
                        f"API GET ERROR {response.status}: "
                        f"{url} -> {text}"
                    )
                    return None

                try:
                    return await response.json()
                except Exception:
                    print(
                        f"API GET INVALID JSON: {url} -> {text}"
                    )
                    return None

    except Exception as e:
        print(f"API GET EXCEPTION: {url} -> {e}")
        return None


async def api_post(path: str, data: dict):
    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(url, json=data) as response:

                text = await response.text()

                if response.status not in (200, 201):
                    print(
                        f"API POST ERROR {response.status}: "
                        f"{url} -> {text}"
                    )
                    return None

                try:
                    return await response.json()
                except Exception:
                    print(
                        f"API POST INVALID JSON: {url} -> {text}"
                    )
                    return None

    except Exception as e:
        print(f"API POST EXCEPTION: {url} -> {e}")
        return None


async def api_delete(path: str):
    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(total=15)

        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.delete(url) as response:

                text = await response.text()

                if response.status not in (200, 204):
                    print(
                        f"API DELETE ERROR {response.status}: "
                        f"{url} -> {text}"
                    )
                    return None

                try:
                    return await response.json()
                except Exception:
                    return {
                        "success": True
                    }

    except Exception as e:
        print(f"API DELETE EXCEPTION: {url} -> {e}")
        return None


# ============================================================
# USER
# ============================================================

async def get_user(telegram_id: int):
    result = await api_get(
        f"/api/user/{telegram_id}"
    )

    if not result:
        return None

    if result.get("success") is False:
        return None

    user = result.get("user")

    if user:
        # Добавляем subscription_url из ответа API
        if result.get("subscription_url"):
            user["subscription_url"] = result["subscription_url"]

        # Если API по какой-то причине вернул localhost,
        # строим правильную публичную ссылку самостоятельно.
        token = user.get("token")

        if token:
            user["subscription_url"] = (
                f"{PUBLIC_URL}/sub/{token}"
            )

        return user

    # На случай если API вернул пользователя напрямую
    if result.get("token"):
        token = result["token"]

        result["subscription_url"] = (
            f"{PUBLIC_URL}/sub/{token}"
        )

        return result

    return None


async def create_or_get_user(telegram_id: int):
    # --------------------------------------------------------
    # 1. Сначала пробуем получить существующего пользователя
    # --------------------------------------------------------

    user = await get_user(telegram_id)

    if user and user.get("token"):
        return user

    # --------------------------------------------------------
    # 2. Если пользователя нет или нет токена —
    #    просим API создать/восстановить его
    # --------------------------------------------------------

    created = await api_post(
        "/api/user/create",
        {
            "telegram_id": telegram_id
        }
    )

    if created:
        created_user = created.get("user")

        if created_user:
            token = created_user.get("token")

            if token:
                created_user["subscription_url"] = (
                    f"{PUBLIC_URL}/sub/{token}"
                )

                return created_user

        if created.get("token"):
            token = created["token"]

            created["subscription_url"] = (
                f"{PUBLIC_URL}/sub/{token}"
            )

            return created

    # --------------------------------------------------------
    # 3. Повторный GET
    # --------------------------------------------------------

    user = await get_user(telegram_id)

    if user and user.get("token"):
        return user

    return None


# ============================================================
# КЛАВИАТУРЫ
# ============================================================

def main_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
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
        ]
    )


def back_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⬅️ Назад",
                    callback_data="back",
                )
            ]
        ]
    )


def devices_keyboard(devices):
    buttons = []

    for device in devices:
        device_id = device.get("device_id")

        if not device_id:
            continue

        name = device.get(
            "device_name",
            "Unknown"
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {name}",
                    callback_data=f"delete_device:{device_id}",
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="⬅️ Назад",
                callback_data="back",
            )
        ]
    )

    return InlineKeyboardMarkup(
        inline_keyboard=buttons
    )


# ============================================================
# /START
# ============================================================

@dp.message(Command("start"))
async def start_handler(message: Message):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:
        await message.answer(
            "❌ Не удалось создать пользователя.\n\n"
            "Попробуй ещё раз через несколько секунд."
        )
        return

    token = user.get("token")

    if not token:
        await message.answer(
            "❌ API создал пользователя, "
            "но токен не был получен."
        )
        return

    await message.answer(
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "🧪 Это экспериментальная версия сервиса.\n\n"
        "Здесь можно протестировать:\n"
        "• VLESS-подписку\n"
        "• несколько серверов\n"
        "• лимит устройств\n"
        "• отображение трафика\n"
        "• управление подпиской\n\n"
        "Выбери действие ниже.",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# ПОДПИСКА
# ============================================================

@dp.callback_query(F.data == "subscription")
async def subscription_callback(
    callback: CallbackQuery
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
            "❌ Токен не найден.\n\n"
            "Попробуй нажать кнопку ещё раз.",
            reply_markup=back_keyboard(),
        )
        return

    subscription_url = (
        f"{PUBLIC_URL}/sub/{token}"
    )

    expire = user.get("expire", 0)
    traffic_limit = user.get(
        "traffic_limit",
        0
    )

    traffic_gb = traffic_limit / (
        1024 ** 3
    )

    text = (
        "🔗 <b>Твоя подписка</b>\n\n"
        f"<code>{subscription_url}</code>\n\n"
        f"📦 Лимит: <b>{traffic_gb:.0f} GB</b>\n"
        f"📱 Устройств: "
        f"<b>{user.get('device_limit', 1)}</b>\n\n"
        "Добавь эту ссылку в Happ."
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# /sub
# ============================================================

@dp.message(Command("sub"))
async def subscription_command(
    message: Message
):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:
        await message.answer(
            "❌ Не удалось получить пользователя."
        )
        return

    token = user.get("token")

    if not token:
        await message.answer(
            "❌ Токен не найден."
        )
        return

    subscription_url = (
        f"{PUBLIC_URL}/sub/{token}"
    )

    await message.answer(
        "🔗 <b>Твоя ссылка на подписку:</b>\n\n"
        f"<code>{subscription_url}</code>\n\n"
        "Добавь её в Happ.",
        parse_mode="HTML",
    )


# ============================================================
# ТРАФИК
# ============================================================

@dp.callback_query(F.data == "traffic")
async def traffic_callback(
    callback: CallbackQuery
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:
        await callback.message.edit_text(
            "❌ Не удалось получить данные.",
            reply_markup=back_keyboard(),
        )
        return

    token = user.get("token")

    if not token:
        await callback.message.edit_text(
            "❌ Токен не найден.",
            reply_markup=back_keyboard(),
        )
        return

    traffic = await api_get(
        f"/api/traffic/{token}"
    )

    if not traffic:
        await callback.message.edit_text(
            "❌ Не удалось получить трафик.",
            reply_markup=back_keyboard(),
        )
        return

    upload = traffic.get(
        "upload_human",
        "0 B"
    )

    download = traffic.get(
        "download_human",
        "0 B"
    )

    used = traffic.get(
        "used_human",
        "0 B"
    )

    limit = traffic.get(
        "limit_human",
        "0 B"
    )

    remaining = traffic.get(
        "remaining_human",
        "0 B"
    )

    percent = traffic.get(
        "percent",
        0
    )

    text = (
        "📊 <b>Трафик</b>\n\n"
        f"⬆️ Отправлено: <b>{upload}</b>\n"
        f"⬇️ Получено: <b>{download}</b>\n\n"
        f"📦 Использовано: <b>{used}</b>\n"
        f"📦 Лимит: <b>{limit}</b>\n"
        f"🟢 Осталось: <b>{remaining}</b>\n\n"
        f"📈 Использовано: <b>{percent:.1f}%</b>"
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# УСТРОЙСТВА
# ============================================================

@dp.callback_query(F.data == "devices")
async def devices_callback(
    callback: CallbackQuery
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:
        await callback.message.edit_text(
            "❌ Не удалось получить данные.",
            reply_markup=back_keyboard(),
        )
        return

    token = user.get("token")

    if not token:
        await callback.message.edit_text(
            "❌ Токен не найден.",
            reply_markup=back_keyboard(),
        )
        return

    devices = user.get(
        "devices",
        []
    )

    device_count = user.get(
        "device_count",
        len(devices)
    )

    device_limit = user.get(
        "device_limit",
        1
    )

    if not devices:
        text = (
            "📱 <b>Устройства</b>\n\n"
            "Подключённых устройств пока нет.\n\n"
            f"Лимит: <b>{device_limit}</b>"
        )
    else:
        lines = [
            "📱 <b>Устройства</b>",
            "",
            f"Используется: "
            f"<b>{device_count}/{device_limit}</b>",
            "",
        ]

        for index, device in enumerate(
            devices,
            start=1
        ):
            name = device.get(
                "device_name",
                "Unknown"
            )

            platform = device.get(
                "platform",
                "Unknown"
            )

            lines.append(
                f"{index}. 📱 {name} "
                f"({platform})"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(devices),
        parse_mode="HTML",
    )


# ============================================================
# УДАЛЕНИЕ УСТРОЙСТВА
# ============================================================

@dp.callback_query(
    F.data.startswith("delete_device:")
)
async def delete_device_callback(
    callback: CallbackQuery
):

    await callback.answer()

    device_id = callback.data.split(
        ":",
        1
    )[1]

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
            "❌ Токен не найден.",
            reply_markup=back_keyboard(),
        )
        return

    result = await api_delete(
        f"/api/device/{token}/{device_id}"
    )

    if not result:
        await callback.message.edit_text(
            "❌ Не удалось удалить устройство.",
            reply_markup=back_keyboard(),
        )
        return

    # Обновляем список
    user = await get_user(
        callback.from_user.id
    )

    if not user:
        await callback.message.edit_text(
            "✅ Устройство удалено.",
            reply_markup=back_keyboard(),
        )
        return

    devices = user.get(
        "devices",
        []
    )

    device_count = user.get(
        "device_count",
        len(devices)
    )

    device_limit = user.get(
        "device_limit",
        1
    )

    if not devices:
        text = (
            "📱 <b>Устройства</b>\n\n"
            "Все устройства удалены.\n\n"
            f"Лимит: <b>{device_limit}</b>"
        )
    else:
        lines = [
            "📱 <b>Устройства</b>",
            "",
            f"Используется: "
            f"<b>{device_count}/{device_limit}</b>",
            "",
        ]

        for index, device in enumerate(
            devices,
            start=1
        ):
            name = device.get(
                "device_name",
                "Unknown"
            )

            platform = device.get(
                "platform",
                "Unknown"
            )

            lines.append(
                f"{index}. 📱 {name} "
                f"({platform})"
            )

        text = "\n".join(lines)

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(devices),
        parse_mode="HTML",
    )


# ============================================================
# СЕРВЕРЫ
# ============================================================

@dp.callback_query(F.data == "servers")
async def servers_callback(
    callback: CallbackQuery
):

    await callback.answer()

    servers = await api_get(
        "/api/servers"
    )

    if not servers:
        await callback.message.edit_text(
            "❌ Не удалось получить список серверов.",
            reply_markup=back_keyboard(),
        )
        return

    server_list = servers.get(
        "servers",
        []
    )

    if not server_list:
        await callback.message.edit_text(
            "🌍 Серверов пока нет.",
            reply_markup=back_keyboard(),
        )
        return

    lines = [
        "🌍 <b>Серверы</b>",
        "",
    ]

    for server in server_list:

        name = server.get(
            "name",
            "Неизвестный сервер"
        )

        status = server.get(
            "status",
            "unknown"
        )

        if status == "online":
            status_text = "🟢"
        elif status == "offline":
            status_text = "🔴"
        else:
            status_text = "🟡"

        lines.append(
            f"{status_text} <b>{name}</b>"
        )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# НАЗАД
# ============================================================

@dp.callback_query(F.data == "back")
async def back_callback(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.edit_text(
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# ERROR HANDLER
# ============================================================

@dp.errors()
async def errors_handler(event):
    print(
        "BOT ERROR:",
        event.exception
    )


# ============================================================
# START
# ============================================================

async def main():

    print("================================")
    print("       ixxy VPN LAB BOT")
    print("================================")
    print(
        f"PUBLIC_URL: {PUBLIC_URL}"
    )

    # Важно: только один экземпляр бота
    await bot.delete_webhook(
        drop_pending_updates=True
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped")