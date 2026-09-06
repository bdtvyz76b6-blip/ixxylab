import os
import secrets
import sqlite3
import time
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import PlainTextResponse, JSONResponse


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv("DB_PATH", "ixxy_lab.db")

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8000"
).rstrip("/")

# Лимит по умолчанию: 50 GB
DEFAULT_TRAFFIC_LIMIT = 50 * 1024 * 1024 * 1024

# 1 устройство
DEFAULT_DEVICE_LIMIT = 1

# Бесплатная подписка на 30 дней
DEFAULT_DAYS = 30

# Сюда позже вставим реальные VLESS-ноды.
# Формат:
# vless://UUID@HOST:PORT?...#Название
VLESS_SERVERS = [
    # "vless://...",
]


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="ixxy VPN LAB",
    version="1.0.0"
)


# ============================================================
# DATABASE
# ============================================================

def db():
    connection = sqlite3.connect(
        DB_PATH,
        check_same_thread=False
    )
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = db()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE,
            token TEXT UNIQUE NOT NULL,
            expire INTEGER NOT NULL,
            traffic_limit INTEGER NOT NULL DEFAULT 0,
            upload INTEGER NOT NULL DEFAULT 0,
            download INTEGER NOT NULL DEFAULT 0,
            device_limit INTEGER NOT NULL DEFAULT 1,
            created_at INTEGER NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            device_id TEXT NOT NULL,
            device_name TEXT DEFAULT 'Unknown',
            platform TEXT DEFAULT 'Unknown',
            first_seen INTEGER NOT NULL,
            last_seen INTEGER NOT NULL,
            active INTEGER NOT NULL DEFAULT 1,

            UNIQUE(user_id, device_id),

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
    """)

    connection.commit()
    connection.close()


init_db()


# ============================================================
# HELPERS
# ============================================================

def now():
    return int(time.time())


def format_bytes(value):
    value = float(value)

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB"
    ]

    for unit in units:
        if value < 1024:
            return f"{value:.2f} {unit}"

        value /= 1024

    return f"{value:.2f} PB"


def get_user_by_token(token):
    connection = db()

    user = connection.execute(
        "SELECT * FROM users WHERE token = ?",
        (token,)
    ).fetchone()

    connection.close()

    return user


def get_user_by_telegram(telegram_id):
    connection = db()

    user = connection.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    connection.close()

    return user


def create_user(telegram_id):
    token = secrets.token_urlsafe(32)

    expire = now() + DEFAULT_DAYS * 86400

    connection = db()

    connection.execute("""
        INSERT INTO users (
            telegram_id,
            token,
            expire,
            traffic_limit,
            device_limit,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        telegram_id,
        token,
        expire,
        DEFAULT_TRAFFIC_LIMIT,
        DEFAULT_DEVICE_LIMIT,
        now()
    ))

    connection.commit()

    user = connection.execute(
        "SELECT * FROM users WHERE telegram_id = ?",
        (telegram_id,)
    ).fetchone()

    connection.close()

    return user


def get_or_create_user(telegram_id):
    user = get_user_by_telegram(telegram_id)

    if user:
        return user

    return create_user(telegram_id)


# ============================================================
# DEVICE SYSTEM
# ============================================================

def get_devices(user_id):
    connection = db()

    devices = connection.execute("""
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND active = 1
        ORDER BY first_seen ASC
    """, (user_id,)).fetchall()

    connection.close()

    return devices


def register_device(
    user_id,
    device_id,
    device_name="Unknown",
    platform="Unknown"
):
    connection = db()

    existing = connection.execute("""
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
    """, (
        user_id,
        device_id
    )).fetchone()

    if existing:
        connection.execute("""
            UPDATE devices
            SET
                device_name = ?,
                platform = ?,
                last_seen = ?,
                active = 1
            WHERE id = ?
        """, (
            device_name,
            platform,
            now(),
            existing["id"]
        ))

        connection.commit()
        connection.close()

        return {
            "success": True,
            "new": False
        }

    user = connection.execute(
        "SELECT device_limit FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    active_count = connection.execute("""
        SELECT COUNT(*)
        FROM devices
        WHERE user_id = ?
          AND active = 1
    """, (user_id,)).fetchone()[0]

    if active_count >= user["device_limit"]:
        connection.close()

        return {
            "success": False,
            "error": "device_limit"
        }

    connection.execute("""
        INSERT INTO devices (
            user_id,
            device_id,
            device_name,
            platform,
            first_seen,
            last_seen
        )
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        device_id,
        device_name,
        platform,
        now(),
        now()
    ))

    connection.commit()
    connection.close()

    return {
        "success": True,
        "new": True
    }


def delete_device(user_id, device_id):
    connection = db()

    cursor = connection.execute("""
        UPDATE devices
        SET active = 0
        WHERE user_id = ?
          AND device_id = ?
    """, (
        user_id,
        device_id
    ))

    connection.commit()
    connection.close()

    return cursor.rowcount > 0


# ============================================================
# TRAFFIC
# ============================================================

def get_traffic(user):
    used = user["upload"] + user["download"]
    limit = user["traffic_limit"]

    if limit > 0:
        percent = min(
            100,
            (used / limit) * 100
        )
    else:
        percent = 0

    return {
        "upload": user["upload"],
        "download": user["download"],
        "used": used,
        "limit": limit,
        "percent": round(percent, 2)
    }


# ============================================================
# SUBSCRIPTION INFO
# ============================================================

def subscription_header(user):
    return (
        f"upload={user['upload']};"
        f"download={user['download']};"
        f"total={user['traffic_limit']};"
        f"expire={user['expire']}"
    )


# ============================================================
# HEALTH
# ============================================================

@app.get("/")
async def root():
    return {
        "service": "ixxy VPN LAB",
        "status": "online"
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "time": now()
    }


# ============================================================
# USER INFO
# ============================================================

@app.get("/api/user/{token}")
async def user_info(token: str):
    user = get_user_by_token(token)

    if not user:
        return JSONResponse(
            {
                "error": "user_not_found"
            },
            status_code=404
        )

    devices = get_devices(user["id"])
    traffic = get_traffic(user)

    return {
        "token": user["token"],
        "expire": user["expire"],
        "traffic": traffic,
        "devices": [
            {
                "id": device["device_id"],
                "name": device["device_name"],
                "platform": device["platform"],
                "first_seen": device["first_seen"],
                "last_seen": device["last_seen"]
            }
            for device in devices
        ],
        "device_count": len(devices),
        "device_limit": user["device_limit"]
    }


# ============================================================
# DEVICE REGISTER
# ============================================================

@app.post("/api/device/register")
async def api_register_device(request: Request):
    data = await request.json()

    token = data.get("token")
    device_id = data.get("device_id")
    device_name = data.get(
        "device_name",
        "Unknown"
    )
    platform = data.get(
        "platform",
        "Unknown"
    )

    if not token or not device_id:
        return JSONResponse(
            {
                "success": False,
                "error": "missing_data"
            },
            status_code=400
        )

    user = get_user_by_token(token)

    if not user:
        return JSONResponse(
            {
                "success": False,
                "error": "invalid_token"
            },
            status_code=404
        )

    result = register_device(
        user["id"],
        device_id,
        device_name,
        platform
    )

    if not result["success"]:
        return JSONResponse(
            {
                "success": False,
                "error": "device_limit",
                "message": "Device limit exceeded"
            },
            status_code=403
        )

    return result


# ============================================================
# DEVICE DELETE
# ============================================================

@app.delete("/api/device/{token}/{device_id}")
async def api_delete_device(
    token: str,
    device_id: str
):
    user = get_user_by_token(token)

    if not user:
        return JSONResponse(
            {
                "success": False,
                "error": "invalid_token"
            },
            status_code=404
        )

    deleted = delete_device(
        user["id"],
        device_id
    )

    return {
        "success": deleted
    }


# ============================================================
# HAPP SUBSCRIPTION
# ============================================================

@app.get("/sub/{token}")
async def subscription(token: str):
    user = get_user_by_token(token)

    if not user:
        return PlainTextResponse(
            "# ixxy VPN\nSubscription not found",
            status_code=404
        )

    if user["expire"] <= now():
        return PlainTextResponse(
            "# ixxy VPN\nSubscription expired",
            status_code=403
        )

    headers = {
        "subscription-userinfo":
            subscription_header(user),

        "profile-title":
            "ixxy VPN LAB",

        "profile-update-interval":
            "60"
    }

    content = "\n".join(
        VLESS_SERVERS
    )

    return PlainTextResponse(
        content,
        headers=headers
    )


# ============================================================
# ADMIN / DEBUG
# ============================================================

@app.get("/api/stats")
async def stats():
    connection = db()

    users = connection.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    devices = connection.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE active = 1
        """
    ).fetchone()[0]

    connection.close()

    return {
        "users": users,
        "active_devices": devices
    }