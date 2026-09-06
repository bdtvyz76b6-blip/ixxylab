import os
import secrets
import sqlite3
import time

from datetime import datetime, timedelta
from urllib.parse import unquote

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel


# ============================================================
# CONFIG
# ============================================================

DB_PATH = os.getenv("DB_PATH", "ixxy_lab.db")

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "http://localhost:8000"
).rstrip("/")

DEFAULT_TRAFFIC_LIMIT = 50 * 1024 * 1024 * 1024  # 50 GB
DEFAULT_DEVICE_LIMIT = 1
DEFAULT_DAYS = 30


# ============================================================
# VLESS SERVERS
# ============================================================

VLESS_SERVERS = [
    "vless://c11b64d6-66dd-0002-9b57-459cd6469939@94.185.83.38:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=diffoscope.com&fp=chrome&pbk=6VMgXXhZdJCiOG05EyK_zTHh00kpFGrZJeZIEPgqhjY&sid=1c3e8241a8743df9#🇸🇪 Швеция",

    "vless://c5694dc5-39fd-4a92-8430-3837baa522a3@pl.bubahero.com:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=pl.bubahero.com&fp=chrome&pbk=GmZv3anSeAeHr_cMFKr-6MPLli-nyKNatnY6P3AFK00&type=tcp&sid=9c2378562188c3cb#🇵🇱 Польша",

    "vless://190fd6c7-0159-446a-a981-bd7115c8ccc5@boldheron.download:443?encryption=none&security=reality&sni=localhost&fp=firefox&pbk=F2VfBr2UmjDTErB_oruvW5aIvzH_xGfM2AW5_w-DF0I&type=tcp&headerType=none#🇩🇪 Германия",

    "vless://0439395e-a77e-4b01-82b5-e114db09ff72@brightharbor.download:443?encryption=none&flow=xtls-rprx-vision&security=reality&sni=localhost&fp=firefox&pbk=F2VfBr2UmjDTErB_oruvW5aIvzH_xGfM2AW5_w-DF0I&type=tcp&headerType=none#🇫🇮 Финляндия",

    "vless://0439395e-a77e-4b01-82b5-e114db09ff72@calmcedar.download:443?encryption=none&security=reality&sni=localhost&fp=chrome&pbk=F2VfBr2UmjDTErB_oruvW5aIvzH_xGfM2AW5_w-DF0I&type=tcp&headerType=none#🇮🇹 Италия",

    "vless://190fd6c7-0159-446a-a981-bd7115c8ccc5@quietmeadow.download:443?encryption=none&security=reality&sni=localhost&fp=firefox&pbk=RYnbBzo-UTB4nVMymzJ5B6TgYed7DfOc6O5Pr_htYSc&type=tcp&headerType=none#🇬🇧 Британия",

    "vless://c11b64d6-66dd-4c55-9b57-459cd6469939@media-se.compressor.work:14443?encryption=none&security=tls&sni=media-se.compressor.work&fp=chrome&type=ws&host=media-se.compressor.work&path=/ws#🇷🇺 LTE #1 ⚡️ | ALL",

    "vless://39d927a4-b8c7-4dc7-91f1-8b2e05d8b6b6@78.159.240.41:443?encryption=none&security=reality&sni=id.vk.com&fp=firefox&pbk=SbVKOEMjK0sIlbwg4akyBg5mL5KZwwB-ed4eEE7YnRc&type=grpc&serviceName=vless-grpc-reality#🇷🇺 LTE #2 ⚡️ | ALL",

    "vless://39d927a4-b8c7-4dc7-91f1-8b2e05d8b6b6@78.159.240.41:443?encryption=none&security=reality&sni=id.vk.com&fp=qq&pbk=SbVKOEMjK0sIlbwg4akyBg5mL5KZwwB-ed4eEE7YnRc&type=grpc&serviceName=vless-grpc-reality#🇷🇺 LTE #3 ⚡️ | ALL",

    "vless://39d927a4-b8c7-4dc7-91f1-8b2e05d8b6b6@78.159.240.41:443?encryption=none&security=reality&sni=id.vk.com&fp=safari&pbk=SbVKOEMjK0sIlbwg4akyBg5mL5KZwwB-ed4eEE7YnRc&type=grpc&serviceName=vless-grpc-reality#🇷🇺 LTE #4 ⚡️ | ALL",
]


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="ixxy VPN LAB",
    version="1.0.0",
    description="Experimental VPN subscription API",
)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()

    conn.execute(
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

    conn.execute(
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
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
        """
    )

    conn.commit()
    conn.close()


init_db()


# ============================================================
# HELPERS
# ============================================================

def now() -> int:
    return int(time.time())


def format_bytes(value: int) -> str:
    value = max(0, int(value))

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
        "PB",
    ]

    size = float(value)

    for unit in units:
        if size < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(size)} {unit}"

            if size >= 10:
                return f"{size:.0f} {unit}"

            return f"{size:.1f} {unit}"

        size /= 1024

    return "0 B"


def row_to_dict(row):
    if row is None:
        return None

    return dict(row)


def get_user_by_token(token: str):
    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE token = ?
        """,
        (token,),
    ).fetchone()

    conn.close()

    return row_to_dict(row)


def get_user_by_telegram(telegram_id: int):
    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM users
        WHERE telegram_id = ?
        """,
        (telegram_id,),
    ).fetchone()

    conn.close()

    return row_to_dict(row)


def create_user(
    telegram_id: int,
    days: int = DEFAULT_DAYS,
    traffic_limit: int = DEFAULT_TRAFFIC_LIMIT,
    device_limit: int = DEFAULT_DEVICE_LIMIT,
):
    token = secrets.token_urlsafe(32)
    created = now()
    expire = created + days * 86400

    conn = db()

    conn.execute(
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
        VALUES (?, ?, ?, ?, 0, 0, ?, ?)
        """,
        (
            telegram_id,
            token,
            expire,
            traffic_limit,
            device_limit,
            created,
        ),
    )

    conn.commit()
    conn.close()

    return get_user_by_telegram(telegram_id)


def get_or_create_user(telegram_id: int):
    user = get_user_by_telegram(telegram_id)

    if user:
        return user

    return create_user(telegram_id)


def get_devices(user_id: int):
    conn = db()

    rows = conn.execute(
        """
        SELECT
            id,
            device_id,
            device_name,
            platform,
            first_seen,
            last_seen,
            active
        FROM devices
        WHERE user_id = ?
        ORDER BY last_seen DESC
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    return [dict(row) for row in rows]


def register_device(
    user_id: int,
    device_id: str,
    device_name: str = "Unknown",
    platform: str = "Unknown",
):
    current = now()

    conn = db()

    user = conn.execute(
        """
        SELECT device_limit
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    if not user:
        conn.close()
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    existing = conn.execute(
        """
        SELECT id
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
        """,
        (user_id, device_id),
    ).fetchone()

    if existing:
        conn.execute(
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
                current,
                existing["id"],
            ),
        )

        conn.commit()
        conn.close()

        return {
            "success": True,
            "existing": True,
        }

    active_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE user_id = ?
          AND active = 1
        """,
        (user_id,),
    ).fetchone()[0]

    if active_count >= user["device_limit"]:
        conn.close()

        raise HTTPException(
            status_code=403,
            detail={
                "error": "device_limit_reached",
                "limit": user["device_limit"],
            },
        )

    conn.execute(
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
            current,
            current,
        ),
    )

    conn.commit()
    conn.close()

    return {
        "success": True,
        "existing": False,
    }


def delete_device(user_id: int, device_id: str):
    conn = db()

    result = conn.execute(
        """
        UPDATE devices
        SET active = 0
        WHERE user_id = ?
          AND device_id = ?
        """,
        (
            user_id,
            device_id,
        ),
    )

    conn.commit()
    conn.close()

    return result.rowcount > 0


def get_traffic(user_id: int):
    conn = db()

    row = conn.execute(
        """
        SELECT
            upload,
            download,
            traffic_limit
        FROM users
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()

    conn.close()

    if not row:
        return None

    upload = int(row["upload"])
    download = int(row["download"])
    total = upload + download
    limit = int(row["traffic_limit"])

    remaining = max(0, limit - total)

    if limit > 0:
        percent = min(
            100,
            round(total / limit * 100, 2),
        )
    else:
        percent = 0

    return {
        "upload": upload,
        "download": download,
        "used": total,
        "limit": limit,
        "remaining": remaining,
        "percent": percent,
        "upload_human": format_bytes(upload),
        "download_human": format_bytes(download),
        "used_human": format_bytes(total),
        "limit_human": format_bytes(limit),
        "remaining_human": format_bytes(remaining),
    }


# ============================================================
# HAPP SUBSCRIPTION HEADERS
# ============================================================

def subscription_header(user):
    upload = int(user["upload"])
    download = int(user["download"])
    total = int(user["traffic_limit"])
    expire = int(user["expire"])

    return (
        f"upload={upload}; "
        f"download={download}; "
        f"total={total}; "
        f"expire={expire}"
    )


# ============================================================
# MODELS
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
def root():
    return {
        "service": "ixxy VPN LAB",
        "status": "online",
        "version": "1.0.0",
        "servers": len(VLESS_SERVERS),
    }


# ============================================================
# HEALTH
# ============================================================

@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": "ixxy VPN LAB",
        "time": now(),
    }


# ============================================================
# CREATE USER
# ============================================================

@app.post("/api/user/create")
def api_create_user(data: CreateUserRequest):
    user = get_or_create_user(data.telegram_id)

    return {
        "success": True,
        "user": user,
        "subscription_url": (
            f"{PUBLIC_URL}/sub/{user['token']}"
        ),
    }


# ============================================================
# USER BY TELEGRAM ID
# ============================================================

@app.get("/api/user/{telegram_id}")
def api_get_user(telegram_id: int):
    user = get_user_by_telegram(telegram_id)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    traffic = get_traffic(user["id"])
    devices = get_devices(user["id"])

    return {
        "success": True,
        "user": user,
        "subscription_url": (
            f"{PUBLIC_URL}/sub/{user['token']}"
        ),
        "traffic": traffic,
        "devices": devices,
        "device_count": len(
            [d for d in devices if d["active"]]
        ),
    }


# ============================================================
# USER BY TOKEN
# ============================================================

@app.get("/api/token/{token}")
def api_get_token(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Invalid token",
        )

    traffic = get_traffic(user["id"])
    devices = get_devices(user["id"])

    return {
        "success": True,
        "user": user,
        "subscription_url": (
            f"{PUBLIC_URL}/sub/{user['token']}"
        ),
        "traffic": traffic,
        "devices": devices,
    }


# ============================================================
# REGISTER DEVICE
# ============================================================

@app.post("/api/device/register")
def api_register_device(data: RegisterDeviceRequest):
    user = get_user_by_token(data.token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Invalid token",
        )

    if int(user["expire"]) <= now():
        raise HTTPException(
            status_code=403,
            detail="Subscription expired",
        )

    result = register_device(
        user_id=user["id"],
        device_id=data.device_id,
        device_name=data.device_name,
        platform=data.platform,
    )

    return {
        "success": True,
        "device": result,
        "devices": get_devices(user["id"]),
    }


# ============================================================
# DELETE DEVICE
# ============================================================

@app.delete("/api/device/{token}/{device_id}")
def api_delete_device(
    token: str,
    device_id: str,
):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Invalid token",
        )

    deleted = delete_device(
        user_id=user["id"],
        device_id=unquote(device_id),
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    return {
        "success": True,
        "devices": get_devices(user["id"]),
    }


# ============================================================
# TRAFFIC
# ============================================================

@app.get("/api/traffic/{token}")
def api_traffic(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Invalid token",
        )

    traffic = get_traffic(user["id"])

    return {
        "success": True,
        "traffic": traffic,
    }


# ============================================================
# SERVERS
# ============================================================

@app.get("/api/servers")
def api_servers():
    servers = []

    for index, link in enumerate(VLESS_SERVERS, start=1):
        name = f"Server {index}"

        if "#" in link:
            name = unquote(
                link.split("#", 1)[1]
            )

        servers.append(
            {
                "id": index,
                "name": name,
                "link": link,
                "status": "online",
            }
        )

    return {
        "success": True,
        "count": len(servers),
        "servers": servers,
    }


# ============================================================
# HAPP SUBSCRIPTION
# ============================================================

@app.get(
    "/sub/{token}",
    response_class=PlainTextResponse,
)
def subscription(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Subscription not found",
        )

    current = now()

    # --------------------------------------------------------
    # EXPIRED
    # --------------------------------------------------------

    if int(user["expire"]) <= current:
        expired_link = (
            "vless://00000000-0000-0000-0000-000000000000"
            "@expired.invalid:443"
            "?type=tcp"
            "&security=reality"
            "&sni=expired.invalid"
            "&fp=chrome"
            "&pbk=AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
            "&sid="
            "&flow=xtls-rprx-vision"
            "#VPN подписка истекла 🔴"
        )

        headers = {
            "subscription-userinfo": (
                "upload=0; "
                "download=0; "
                "total=0; "
                f"expire={user['expire']}"
            ),
            "profile-title": "ixxy VPN LAB",
            "profile-update-interval": "60",
            "cache-control": "no-cache",
        }

        return PlainTextResponse(
            content=expired_link,
            headers=headers,
            media_type="text/plain; charset=utf-8",
        )

    # --------------------------------------------------------
    # ACTIVE
    # --------------------------------------------------------

    if not VLESS_SERVERS:
        content = (
            "# ixxy VPN LAB\n"
            "# Серверы пока не добавлены\n"
        )

    else:
        content = "\n".join(
            VLESS_SERVERS
        )

    headers = {
        "subscription-userinfo": subscription_header(
            user
        ),
        "profile-title": "ixxy VPN LAB",
        "profile-update-interval": "60",
        "cache-control": "no-cache",
    }

    return PlainTextResponse(
        content=content,
        headers=headers,
        media_type="text/plain; charset=utf-8",
    )


# ============================================================
# ADMIN / GLOBAL STATS
# ============================================================

@app.get("/api/stats")
def api_stats():
    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    active_users = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE expire > ?
        """,
        (now(),),
    ).fetchone()[0]

    expired_users = conn.execute(
        """
        SELECT COUNT(*)
        FROM users
        WHERE expire <= ?
        """,
        (now(),),
    ).fetchone()[0]

    devices = conn.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE active = 1
        """
    ).fetchone()[0]

    upload = conn.execute(
        """
        SELECT COALESCE(SUM(upload), 0)
        FROM users
        """
    ).fetchone()[0]

    download = conn.execute(
        """
        SELECT COALESCE(SUM(download), 0)
        FROM users
        """
    ).fetchone()[0]

    conn.close()

    total_traffic = int(upload) + int(download)

    return {
        "success": True,

        "users": {
            "total": users,
            "active": active_users,
            "expired": expired_users,
        },

        "devices": {
            "active": devices,
        },

        "traffic": {
            "upload": int(upload),
            "download": int(download),
            "total": total_traffic,
            "upload_human": format_bytes(upload),
            "download_human": format_bytes(download),
            "total_human": format_bytes(total_traffic),
        },

        "servers": {
            "total": len(VLESS_SERVERS),
        },
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(
        os.getenv(
            "PORT",
            "8000",
        )
    )

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port,
    )