import os
import asyncio
import hashlib
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

BOT_TOKEN = os.getenv(
    "BOT_TOKEN",
    ""
).strip()

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "https://ixxylab-1.onrender.com",
).rstrip("/")


if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN не задан"
    )


# ============================================================
# BOT
# ============================================================

bot = Bot(
    token=BOT_TOKEN
)

dp = Dispatcher()


# ============================================================
# API
# ============================================================

async def api_get(path: str):

    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(
            total=15
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.get(
                url
            ) as response:

                text = await response.text()

                if response.status != 200:
                    print(
                        f"GET {response.status}: "
                        f"{url} -> {text}"
                    )
                    return None

                try:
                    return await response.json()
                except Exception:
                    print(
                        f"INVALID JSON: "
                        f"{url} -> {text}"
                    )
                    return None

    except Exception as e:
        print(
            f"GET EXCEPTION: {url}: {e}"
        )
        return None


async def api_post(
    path: str,
    data: dict,
):

    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(
            total=15
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.post(
                url,
                json=data,
            ) as response:

                text = await response.text()

                if response.status not in (
                    200,
                    201,
                ):
                    print(
                        f"POST {response.status}: "
                        f"{url} -> {text}"
                    )

                    try:
                        return {
                            "_error": await response.json()
                        }
                    except Exception:
                        return None

                try:
                    return await response.json()
                except Exception:
                    print(
                        f"INVALID JSON: "
                        f"{url} -> {text}"
                    )
                    return None

    except Exception as e:
        print(
            f"POST EXCEPTION: {url}: {e}"
        )
        return None


async def api_delete(path: str):

    url = f"{PUBLIC_URL}{path}"

    try:
        timeout = aiohttp.ClientTimeout(
            total=15
        )

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            async with session.delete(
                url
            ) as response:

                text = await response.text()

                if response.status not in (
                    200,
                    204,
                ):
                    print(
                        f"DELETE {response.status}: "
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
        print(
            f"DELETE EXCEPTION: {url}: {e}"
        )
        return None


# ============================================================
# USER
# ============================================================

async def get_user(
    telegram_id: int
):

    result = await api_get(
        f"/api/user/{telegram_id}"
    )

    if not result:
        return None

    if result.get("success") is False:
        return None

    user = result.get("user")

    if not user:
        return None

    token = user.get("token")

    if token:
        user["subscription_url"] = (
            f"{PUBLIC_URL}/sub/{token}"
        )

    user["devices"] = result.get(
        "devices",
        []
    )

    user["device_count"] = result.get(
        "device_count",
        len(user["devices"])
    )

    return user


async def create_or_get_user(
    telegram_id: int
):

    user = await get_user(
        telegram_id
    )

    if user and user.get("token"):
        return user

    result = await api_post(
        "/api/user/create",
        {
            "telegram_id": telegram_id
        },
    )

    if result:

        user = result.get(
            "user"
        )

        if user and user.get("token"):

            token = user["token"]

            user["subscription_url"] = (
                f"{PUBLIC_URL}/sub/{token}"
            )

            user["devices"] = result.get(
                "devices",
                []
            )

            user["device_count"] = result.get(
                "device_count",
                0
            )

            return user

    return await get_user(
        telegram_id
    )


# ============================================================
# KEYBOARDS
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


def devices_keyboard(
    devices
):

    buttons = []

    for device in devices:

        device_id = device.get(
            "device_id"
        )

        name = device.get(
            "device_name",
            "Unknown",
        )

        buttons.append(
            [
                InlineKeyboardButton(
                    text=f"🗑 {name}",
                    callback_data=(
                        f"delete_device:{device_id}"
                    ),
                )
            ]
        )

    buttons.append(
        [
            InlineKeyboardButton(
                text="➕ Как добавить устройство",
                callback_data="add_device_help",
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
# START
# ============================================================

@dp.message(
    Command("start")
)
async def start_handler(
    message: Message
):

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ Не удалось создать пользователя.\n\n"
            "Попробуй ещё раз."
        )

        return

    await message.answer(
        "🦅 <b>ixxy VPN LAB</b>\n\n"
        "🧪 Экспериментальная версия.\n\n"
        "Здесь тестируем:\n"
        "• VLESS-подписку\n"
        "• серверы\n"
        "• лимит устройств\n"
        "• отображение трафика\n"
        "• управление устройствами\n\n"
        "Выбери действие:",
        reply_markup=main_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# SUBSCRIPTION
# ============================================================

@dp.callback_query(
    F.data == "subscription"
)
async def subscription_callback(
    callback: CallbackQuery
):

    await callback.answer()

    user = await create_or_get_user(
        callback.from_user.id
    )

    if not user:

        await callback.message.edit_text(
            "❌ Не удалось получить пользователя.",
            reply_markup=back_keyboard(),
        )

        return

    token = user.get(
        "token"
    )

    if not token:

        await callback.message.edit_text(
            "❌ Токен не найден.",
            reply_markup=back_keyboard(),
        )

        return

    url = (
        f"{PUBLIC_URL}/sub/{token}"
    )

    expire = user.get(
        "expire",
        0
    )

    traffic_limit = user.get(
        "traffic_limit",
        0
    )

    traffic_gb = (
        traffic_limit
        / (1024 ** 3)
    )

    device_limit = user.get(
        "device_limit",
        1
    )

    devices = user.get(
        "devices",
        []
    )

    text = (
        "🔗 <b>Твоя подписка</b>\n\n"
        f"<code>{url}</code>\n\n"
        f"📦 Лимит трафика: "
        f"<b>{traffic_gb:.0f} GB</b>\n"
        f"📱 Устройства: "
        f"<b>{len(devices)}/{device_limit}</b>\n\n"
        "Добавь ссылку в Happ."
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# /SUB
# ============================================================

@dp.message(
    Command("sub")
)
async def sub_command(
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

    token = user.get(
        "token"
    )

    if not token:

        await message.answer(
            "❌ Токен не найден."
        )

        return

    url = (
        f"{PUBLIC_URL}/sub/{token}"
    )

    await message.answer(
        "🔗 <b>Твоя подписка:</b>\n\n"
        f"<code>{url}</code>",
        parse_mode="HTML",
    )


# ============================================================
# TRAFFIC
# ============================================================

@dp.callback_query(
    F.data == "traffic"
)
async def traffic_callback(
    callback: CallbackQuery
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

    token = user.get(
        "token"
    )

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
        "0 B",
    )

    download = traffic.get(
        "download_human",
        "0 B",
    )

    used = traffic.get(
        "used_human",
        "0 B",
    )

    limit = traffic.get(
        "limit_human",
        "0 B",
    )

    remaining = traffic.get(
        "remaining_human",
        "0 B",
    )

    percent = traffic.get(
        "percent",
        0,
    )

    text = (
        "📊 <b>Трафик</b>\n\n"
        f"⬆️ Отправлено: <b>{upload}</b>\n"
        f"⬇️ Получено: <b>{download}</b>\n\n"
        f"📦 Использовано: <b>{used}</b>\n"
        f"📦 Лимит: <b>{limit}</b>\n"
        f"🟢 Осталось: <b>{remaining}</b>\n\n"
        f"📈 Использовано: "
        f"<b>{percent:.1f}%</b>\n\n"
        "ℹ️ Трафик пока считается "
        "по данным LAB API."
    )

    await callback.message.edit_text(
        text,
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# DEVICES
# ============================================================

@dp.callback_query(
    F.data == "devices"
)
async def devices_callback(
    callback: CallbackQuery
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

    devices = user.get(
        "devices",
        []
    )

    device_limit = user.get(
        "device_limit",
        1
    )

    if not devices:

        text = (
            "📱 <b>Устройства</b>\n\n"
            "Пока ни одного устройства "
            "не зарегистрировано.\n\n"
            f"Лимит: <b>0/{device_limit}</b>\n\n"
            "Для теста отправь:\n"
            "<code>/device iPhone</code>"
        )

    else:

        lines = [
            "📱 <b>Устройства</b>",
            "",
            f"Используется: "
            f"<b>{len(devices)}/{device_limit}</b>",
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

            lines.append(
                f"{index}. 📱 <b>{name}</b>"
            )

            lines.append(
                f"   ОС: {platform}"
            )

        text = "\n".join(
            lines
        )

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(
            devices
        ),
        parse_mode="HTML",
    )


# ============================================================
# ADD DEVICE HELP
# ============================================================

@dp.callback_query(
    F.data == "add_device_help"
)
async def add_device_help(
    callback: CallbackQuery
):

    await callback.answer()

    await callback.message.edit_text(
        "📱 <b>Добавление устройства</b>\n\n"
        "Для теста отправь команду:\n\n"
        "<code>/device iPhone</code>\n\n"
        "Например:\n"
        "<code>/device iPhone</code>\n"
        "<code>/device iPad</code>\n"
        "<code>/device Android</code>\n\n"
        "Если лимит равен 1, второе устройство "
        "будет автоматически заблокировано.",
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# /DEVICE
# ============================================================

@dp.message(
    Command("device")
)
async def device_command(
    message: Message
):

    args = message.text.split(
        maxsplit=1
    )

    if len(args) < 2:
        await message.answer(
            "📱 <b>Добавление устройства</b>\n\n"
            "Используй:\n"
            "<code>/device iPhone</code>\n\n"
            "Примеры:\n"
            "<code>/device iPhone</code>\n"
            "<code>/device iPad</code>\n"
            "<code>/device Android</code>",
            parse_mode="HTML",
        )

        return

    device_name = args[1].strip()

    if len(device_name) > 40:
        device_name = device_name[:40]

    user = await create_or_get_user(
        message.from_user.id
    )

    if not user:

        await message.answer(
            "❌ Пользователь не найден."
        )

        return

    token = user.get(
        "token"
    )

    if not token:

        await message.answer(
            "❌ Токен не найден."
        )

        return

    # Создаём стабильный ID устройства
    raw_id = (
        f"{message.from_user.id}:"
        f"{device_name.lower()}"
    )

    device_id = hashlib.sha256(
        raw_id.encode(
            "utf-8"
        )
    ).hexdigest()[:24]

    # Определяем платформу
    lower = device_name.lower()

    if "iphone" in lower or "ipad" in lower:
        platform = "iOS"

    elif (
        "android" in lower
        or "samsung" in lower
        or "xiaomi" in lower
        or "redmi" in lower
    ):
        platform = "Android"

    elif (
        "windows" in lower
        or "pc" in lower
        or "computer" in lower
    ):
        platform = "Windows"

    elif "mac" in lower:
        platform = "macOS"

    else:
        platform = "Unknown"

    result = await api_post(
        "/api/device/register",
        {
            "token": token,
            "device_id": device_id,
            "device_name": device_name,
            "platform": platform,
        },
    )

    # --------------------------------------------------------
    # ЛИМИТ ДОСТИГНУТ
    # --------------------------------------------------------

    if result and result.get(
        "_error"
    ):

        error = result["_error"]

        detail = error.get(
            "detail",
            {}
        )

        if (
            isinstance(detail, dict)
            and detail.get("error")
            == "device_limit"
        ):

            limit = detail.get(
                "device_limit",
                user.get(
                    "device_limit",
                    1
                ),
            )

            count = detail.get(
                "device_count",
                limit,
            )

            await message.answer(
                "🚫 <b>Лимит устройств достигнут</b>\n\n"
                f"📱 Используется: "
                f"<b>{count}/{limit}</b>\n\n"
                f"Новое устройство "
                f"<b>{device_name}</b> "
                "добавить нельзя.\n\n"
                "Сначала удали одно из "
                "существующих устройств.",
                parse_mode="HTML",
            )

            return

    if not result:

        await message.answer(
            "❌ Не удалось зарегистрировать устройство."
        )

        return

    if result.get(
        "success"
    ):

        devices = result.get(
            "devices",
            []
        )

        device_count = result.get(
            "device_count",
            len(devices)
        )

        device_limit = result.get(
            "device_limit",
            user.get(
                "device_limit",
                1
            )
        )

        await message.answer(
            "✅ <b>Устройство зарегистрировано</b>\n\n"
            f"📱 Устройство: "
            f"<b>{device_name}</b>\n"
            f"💻 Платформа: "
            f"<b>{platform}</b>\n\n"
            f"📊 Лимит: "
            f"<b>{device_count}/{device_limit}</b>",
            parse_mode="HTML",
        )

        return

    await message.answer(
        "❌ Не удалось зарегистрировать устройство."
    )


# ============================================================
# DELETE DEVICE
# ============================================================

@dp.callback_query(
    F.data.startswith(
        "delete_device:"
    )
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

    token = user.get(
        "token"
    )

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

    user = await get_user(
        callback.from_user.id
    )

    devices = (
        user.get(
            "devices",
            []
        )
        if user
        else []
    )

    device_limit = (
        user.get(
            "device_limit",
            1
        )
        if user
        else 1
    )

    if not devices:

        text = (
            "📱 <b>Устройства</b>\n\n"
            "Все устройства удалены.\n\n"
            f"Лимит: <b>0/{device_limit}</b>\n\n"
            "Теперь можно добавить новое."
        )

    else:

        lines = [
            "📱 <b>Устройства</b>",
            "",
            f"Используется: "
            f"<b>{len(devices)}/{device_limit}</b>",
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

            lines.append(
                f"{index}. 📱 <b>{name}</b>"
            )

            lines.append(
                f"   ОС: {platform}"
            )

        text = "\n".join(
            lines
        )

    await callback.message.edit_text(
        text,
        reply_markup=devices_keyboard(
            devices
        ),
        parse_mode="HTML",
    )


# ============================================================
# SERVERS
# ============================================================

@dp.callback_query(
    F.data == "servers"
)
async def servers_callback(
    callback: CallbackQuery
):

    await callback.answer()

    result = await api_get(
        "/api/servers"
    )

    if not result:

        await callback.message.edit_text(
            "❌ Не удалось получить серверы.",
            reply_markup=back_keyboard(),
        )

        return

    servers = result.get(
        "servers",
        []
    )

    if not servers:

        await callback.message.edit_text(
            "🌍 Серверов пока нет.",
            reply_markup=back_keyboard(),
        )

        return

    lines = [
        "🌍 <b>Серверы</b>",
        "",
    ]

    for server in servers:

        name = server.get(
            "name",
            "Unknown",
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
            icon = "⚙️"

        lines.append(
            f"{icon} {name}"
        )

    lines.extend(
        [
            "",
            "⚙️ Статус «configured» означает, "
            "что сервер добавлен в подписку. "
            "LAB пока не проверяет его доступность.",
        ]
    )

    await callback.message.edit_text(
        "\n".join(lines),
        reply_markup=back_keyboard(),
        parse_mode="HTML",
    )


# ============================================================
# BACK
# ============================================================

@dp.callback_query(
    F.data == "back"
)
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
# START BOT
# ============================================================

async def main():

    print(
        "================================"
    )
    print(
        "       ixxy VPN LAB BOT"
    )
    print(
        "================================"
    )
    print(
        f"PUBLIC_URL: {PUBLIC_URL}"
    )

    # Только один экземпляр бота
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
            "Bot stopped"
        )