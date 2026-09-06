import os
import secrets
import sqlite3
import time

from datetime import datetime, timedelta

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv(
    "DB_PATH",
    "ixxy_lab.db"
)

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8000"
).rstrip("/")

DEFAULT_TRAFFIC_LIMIT = (
    50 * 1024 * 1024 * 1024
)  # 50 GB

DEFAULT_DEVICE_LIMIT = 1
DEFAULT_DAYS = 30


# ============================================================
# VLESS SERVERS
# ============================================================
#
# Сюда потом вставим реальные VLESS-ссылки.
#
# Пример:
#
# VLESS_SERVERS = [
#     "vless://UUID@IP:443?...#Finland",
#     "vless://UUID@IP:443?...#Germany",
# ]
#

VLESS_SERVERS = []


# ============================================================
# FASTAPI
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

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            telegram_id INTEGER UNIQUE NOT NULL,

            token TEXT UNIQUE NOT NULL,

            expire INTEGER NOT NULL,

            traffic_limit INTEGER NOT NULL DEFAULT 53687091200,

            upload INTEGER NOT NULL DEFAULT 0,

            download INTEGER NOT NULL DEFAULT 0,

            device_limit INTEGER NOT NULL DEFAULT 1,

            created_at INTEGER NOT NULL
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS devices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            user_id INTEGER NOT NULL,

            device_id TEXT NOT NULL,

            device_name TEXT NOT NULL DEFAULT 'Unknown',

            platform TEXT NOT NULL DEFAULT 'Unknown',

            first_seen INTEGER NOT NULL,

            last_seen INTEGER NOT NULL,

            active INTEGER NOT NULL DEFAULT 1,

            UNIQUE(user_id, device_id),

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

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

    if value < 1024:
        return f"{value:.0f} B"

    if value < 1024 ** 2:
        return f"{value / 1024:.2f} KB"

    if value < 1024 ** 3:
        return f"{value / 1024 ** 2:.2f} MB"

    if value < 1024 ** 4:
        return f"{value / 1024 ** 3:.2f} GB"

    return f"{value / 1024 ** 4:.2f} TB"


def row_to_dict(row):

    if not row:
        return None

    return dict(row)


# ============================================================
# USERS
# ============================================================

def get_user_by_token(token):

    connection = db()

    row = connection.execute(
        """
        SELECT *
        FROM users
        WHERE token = ?
        """,
        (token,)
    ).fetchone()

    connection.close()

    return row_to_dict(row)


def get_user_by_telegram(telegram_id):

    connection = db()

    row = connection.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,)
    ).fetchone()

    connection.close()

    return row_to_dict(row)


def create_user(telegram_id):

    existing = get_user_by_telegram(
        telegram_id
    )

    if existing:
        return existing

    created_at = now()

    expire = int(
        (
            datetime.now()
            + timedelta(days=DEFAULT_DAYS)
        ).timestamp()
    )

    token = secrets.token_urlsafe(32)

    connection = db()

    connection.execute(
        """
        INSERT INTO users (
            telegram_id,
            token,
            expire,
            traffic_limit,
            upload,
            download,
            device_limit,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            telegram_id,
            token,
            expire,
            DEFAULT_TRAFFIC_LIMIT,
            0,
            0,
            DEFAULT_DEVICE_LIMIT,
            created_at
        )
    )

    connection.commit()
    connection.close()

    return get_user_by_telegram(
        telegram_id
    )


def get_or_create_user(telegram_id):

    user = get_user_by_telegram(
        telegram_id
    )

    if user:
        return user

    return create_user(
        telegram_id
    )


# ============================================================
# DEVICES
# ============================================================

def get_devices(user_id):

    connection = db()

    rows = connection.execute(
        """
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND active = 1
        ORDER BY first_seen ASC
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return [
        dict(row)
        for row in rows
    ]


def register_device(
    user_id,
    device_id,
    device_name="Unknown",
    platform="Unknown"
):

    connection = db()

    existing = connection.execute(
        """
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
        """,
        (
            user_id,
            device_id
        )
    ).fetchone()

    current_count = connection.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE user_id = ?
          AND active = 1
        """,
        (user_id,)
    ).fetchone()[0]

    user = connection.execute(
        """
        SELECT device_limit
        FROM users
        WHERE id = ?
        """,
        (user_id,)
    ).fetchone()

    device_limit = (
        user["device_limit"]
        if user
        else DEFAULT_DEVICE_LIMIT
    )

    current_time = now()

    # Уже существует
    if existing:

        connection.execute(
            """
            UPDATE devices
            SET
                device_name = ?,
                platform = ?,
                last_seen = ?,
                active = 1
            WHERE id = ?
            """,
            (
                device_name,
                platform,
                current_time,
                existing["id"]
            )
        )

        connection.commit()
        connection.close()

        return {
            "success": True,
            "created": False,
            "device": dict(existing)
        }

    # Лимит устройств
    if current_count >= device_limit:

        connection.close()

        return {
            "success": False,
            "error": "device_limit",
            "message": "Device limit exceeded"
        }

    cursor = connection.execute(
        """
        INSERT INTO devices (
            user_id,
            device_id,
            device_name,
            platform,
            first_seen,
            last_seen,
            active
        )
        VALUES (?, ?, ?, ?, ?, ?, 1)
        """,
        (
            user_id,
            device_id,
            device_name,
            platform,
            current_time,
            current_time
        )
    )

    connection.commit()

    device_id_db = cursor.lastrowid

    row = connection.execute(
        """
        SELECT *
        FROM devices
        WHERE id = ?
        """,
        (device_id_db,)
    ).fetchone()

    connection.close()

    return {
        "success": True,
        "created": True,
        "device": dict(row)
    }


def delete_device(
    user_id,
    device_id
):

    connection = db()

    cursor = connection.execute(
        """
        UPDATE devices
        SET active = 0
        WHERE user_id = ?
          AND (
              id = ?
              OR device_id = ?
          )
        """,
        (
            user_id,
            device_id,
            device_id
        )
    )

    connection.commit()

    changed = cursor.rowcount

    connection.close()

    return changed > 0


# ============================================================
# TRAFFIC
# ============================================================

def get_traffic(user):

    upload = int(
        user.get("upload", 0)
        or 0
    )

    download = int(
        user.get("download", 0)
        or 0
    )

    limit = int(
        user.get("traffic_limit", 0)
        or 0
    )

    used = upload + download

    if limit > 0:
        percent = (
            used / limit
        ) * 100

        percent = min(
            100,
            percent
        )

    else:
        percent = 0

    return {
        "upload": upload,
        "download": download,
        "used": used,
        "limit": limit,
        "percent": percent,
        "upload_human": format_bytes(upload),
        "download_human": format_bytes(download),
        "used_human": format_bytes(used),
        "limit_human": format_bytes(limit),
    }


# ============================================================
# HAPP
# ============================================================

def subscription_header(user):

    upload = int(
        user.get("upload", 0)
        or 0
    )

    download = int(
        user.get("download", 0)
        or 0
    )

    total = int(
        user.get("traffic_limit", 0)
        or 0
    )

    expire = int(
        user.get("expire", 0)
        or 0
    )

    return (
        f"upload={upload};"
        f"download={download};"
        f"total={total};"
        f"expire={expire}"
    )


# ============================================================
# API MODELS
# ============================================================

class CreateUserRequest(BaseModel):
    telegram_id: int


class RegisterDeviceRequest(BaseModel):
    token: str
    device_id: str
    device_name: str = "Unknown"
    platform: str = "Unknown"


# ============================================================
# ROOT
# ============================================================

@app.get("/")
async def root():

    return {
        "service": "ixxy VPN LAB",
        "status": "online",
        "version": "1.0.0"
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
async def health():

    return {
        "status": "ok",
        "time": now()
    }


# ============================================================
# CREATE USER
# ============================================================

@app.post("/api/user/create")
async def api_create_user(
    request: CreateUserRequest
):

    user = get_or_create_user(
        request.telegram_id
    )

    return {
        "success": True,
        "user": user
    }


# ============================================================
# USER INFO
# ============================================================

@app.get("/api/user/{telegram_id}")
async def api_user(
    telegram_id: int
):

    user = get_user_by_telegram(
        telegram_id
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="User not found"
        )

    devices = get_devices(
        user["id"]
    )

    traffic = get_traffic(
        user
    )

    return {
        "telegram_id": user["telegram_id"],

        "token": user["token"],

        "expire": user["expire"],

        "traffic": traffic,

        "device_count": len(devices),

        "device_limit": user["device_limit"],

        "devices": devices,

        "subscription_url":
            f"{PUBLIC_URL}/sub/{user['token']}"
    }


# ============================================================
# USER BY TOKEN
# ============================================================

@app.get("/api/token/{token}")
async def api_token(
    token: str
):

    user = get_user_by_token(
        token
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Invalid token"
        )

    devices = get_devices(
        user["id"]
    )

    traffic = get_traffic(
        user
    )

    return {
        "telegram_id": user["telegram_id"],
        "token": user["token"],
        "expire": user["expire"],
        "traffic": traffic,
        "device_count": len(devices),
        "device_limit": user["device_limit"],
        "devices": devices
    }


# ============================================================
# REGISTER DEVICE
# ============================================================

@app.post("/api/device/register")
async def api_register_device(
    request: RegisterDeviceRequest
):

    user = get_user_by_token(
        request.token
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Invalid token"
        )

    result = register_device(
        user_id=user["id"],
        device_id=request.device_id,
        device_name=request.device_name,
        platform=request.platform
    )

    if not result["success"]:

        raise HTTPException(
            status_code=403,
            detail="Device limit exceeded"
        )

    return result


# ============================================================
# DELETE DEVICE
# ============================================================

@app.delete(
    "/api/device/{token}/{device_id}"
)
async def api_delete_device(
    token: str,
    device_id: str
):

    user = get_user_by_token(
        token
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Invalid token"
        )

    success = delete_device(
        user["id"],
        device_id
    )

    return {
        "success": success
    }


# ============================================================
# SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse
)
async def subscription(
    token: str
):

    user = get_user_by_token(
        token
    )

    if not user:

        raise HTTPException(
            status_code=404,
            detail="Subscription not found"
        )

    # ========================================================
    # EXPIRED
    # ========================================================

    if user["expire"] <= now():

        return PlainTextResponse(
            content=(
                "# ixxy VPN\n"
                "# Subscription expired\n"
            ),
            headers={
                "profile-title":
                    "ixxy VPN LAB — Expired",

                "profile-update-interval":
                    "60",

                "subscription-userinfo":
                    subscription_header(user)
            }
        )

    # ========================================================
    # SERVERS
    # ========================================================

    content = ""

    for server in VLESS_SERVERS:

        content += server.strip()
        content += "\n"

    # Если серверов пока нет
    if not content:

        content = (
            "# ixxy VPN LAB\n"
            "# No servers configured yet\n"
        )

    # ========================================================
    # RESPONSE
    # ========================================================

    return PlainTextResponse(
        content=content,
        headers={
            "subscription-userinfo":
                subscription_header(user),

            "profile-title":
                "ixxy VPN LAB",

            "profile-update-interval":
                "60",

            "cache-control":
                "no-cache"
        }
    )


# ============================================================
# STATS
# ============================================================

@app.get("/api/stats")
async def api_stats():

    connection = db()

    users = connection.execute(
        """
        SELECT COUNT(*)
        FROM users
        """
    ).fetchone()[0]

    active_devices = connection.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE active = 1
        """
    ).fetchone()[0]

    traffic = connection.execute(
        """
        SELECT
            COALESCE(SUM(upload), 0),
            COALESCE(SUM(download), 0)
        FROM users
        """
    ).fetchone()

    connection.close()

    upload = int(
        traffic[0] or 0
    )

    download = int(
        traffic[1] or 0
    )

    return {
        "users": users,

        "active_devices":
            active_devices,

        "upload": upload,

        "download": download,

        "total_traffic":
            upload + download,

        "upload_human":
            format_bytes(upload),

        "download_human":
            format_bytes(download),

        "total_traffic_human":
            format_bytes(
                upload + download
            )
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":

    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000"
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )