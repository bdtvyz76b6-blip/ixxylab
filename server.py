import os
import secrets
import sqlite3
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel


# ============================================================
# НАСТРОЙКИ
# ============================================================

DB_PATH = os.getenv("DB_PATH", "ixxy_lab.db")

PUBLIC_URL = os.getenv(
    "PUBLIC_URL",
    "https://ixxylab-1.onrender.com",
).rstrip("/")

DEFAULT_TRAFFIC_LIMIT = 50 * 1024 * 1024 * 1024  # 50 GB
DEFAULT_DEVICE_LIMIT = 1
DEFAULT_DAYS = 30


# ============================================================
# VLESS СЕРВЕРЫ
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
# FASTAPI
# ============================================================

app = FastAPI(
    title="ixxy VPN LAB",
    version="2.0",
)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
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

            FOREIGN KEY(user_id)
                REFERENCES users(id)
                ON DELETE CASCADE
        )
        """
    )

    conn.commit()
    conn.close()


@app.on_event("startup")
def startup():
    init_db()


# ============================================================
# HELPERS
# ============================================================

def now():
    return int(time.time())


def format_bytes(value: int) -> str:
    value = max(0, int(value))

    units = [
        "B",
        "KB",
        "MB",
        "GB",
        "TB",
    ]

    size = float(value)

    for unit in units:
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} B"

            return f"{size:.2f} {unit}"

        size /= 1024

    return f"{size:.2f} TB"


def row_to_dict(row):
    if not row:
        return None

    return dict(row)


# ============================================================
# USERS
# ============================================================

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

    return row


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

    return row


def create_user(telegram_id: int):
    existing = get_user_by_telegram(telegram_id)

    if existing:
        data = row_to_dict(existing)

        # Ремонт пустого токена
        if not data.get("token"):
            token = secrets.token_urlsafe(32)

            conn = db()

            conn.execute(
                """
                UPDATE users
                SET token = ?
                WHERE telegram_id = ?
                """,
                (
                    token,
                    telegram_id,
                ),
            )

            conn.commit()
            conn.close()

            existing = get_user_by_telegram(
                telegram_id
            )

        return row_to_dict(existing)

    token = secrets.token_urlsafe(32)

    current = now()

    expire = current + (
        DEFAULT_DAYS * 24 * 60 * 60
    )

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
            DEFAULT_TRAFFIC_LIMIT,
            DEFAULT_DEVICE_LIMIT,
            current,
        ),
    )

    conn.commit()
    conn.close()

    return row_to_dict(
        get_user_by_telegram(telegram_id)
    )


def get_or_create_user(telegram_id: int):
    return create_user(telegram_id)


# ============================================================
# DEVICES
# ============================================================

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
          AND active = 1
        ORDER BY first_seen ASC
        """,
        (user_id,),
    ).fetchall()

    conn.close()

    return [
        dict(row)
        for row in rows
    ]


def register_device(
    user_id: int,
    device_id: str,
    device_name: str,
    platform: str,
):
    conn = db()

    # Уже зарегистрировано
    existing = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
        """,
        (
            user_id,
            device_id,
        ),
    ).fetchone()

    current = now()

    if existing:
        conn.execute(
            """
            UPDATE devices
            SET
                device_name = ?,
                platform = ?,
                last_seen = ?,
                active = 1
            WHERE user_id = ?
              AND device_id = ?
            """,
            (
                device_name,
                platform,
                current,
                user_id,
                device_id,
            ),
        )

        conn.commit()

        row = conn.execute(
            """
            SELECT *
            FROM devices
            WHERE user_id = ?
              AND device_id = ?
            """,
            (
                user_id,
                device_id,
            ),
        ).fetchone()

        conn.close()

        return {
            "success": True,
            "already_registered": True,
            "device": dict(row),
        }

    # Получаем лимит пользователя
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
        return {
            "success": False,
            "error": "user_not_found",
        }

    device_limit = int(
        user["device_limit"]
    )

    active_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE user_id = ?
          AND active = 1
        """,
        (user_id,),
    ).fetchone()[0]

    if active_count >= device_limit:
        conn.close()

        return {
            "success": False,
            "error": "device_limit",
            "device_limit": device_limit,
            "device_count": active_count,
        }

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

    row = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
        """,
        (
            user_id,
            device_id,
        ),
    ).fetchone()

    conn.close()

    return {
        "success": True,
        "already_registered": False,
        "device": dict(row),
    }


def delete_device(
    user_id: int,
    device_id: str,
):
    conn = db()

    row = conn.execute(
        """
        SELECT *
        FROM devices
        WHERE user_id = ?
          AND device_id = ?
          AND active = 1
        """,
        (
            user_id,
            device_id,
        ),
    ).fetchone()

    if not row:
        conn.close()

        return False

    conn.execute(
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

    return True


# ============================================================
# TRAFFIC
# ============================================================

def get_traffic(user):
    upload = int(user["upload"])
    download = int(user["download"])
    limit = int(user["traffic_limit"])

    used = upload + download

    remaining = max(
        0,
        limit - used
    )

    if limit > 0:
        percent = (
            used / limit
        ) * 100
    else:
        percent = 0

    return {
        "upload": upload,
        "download": download,
        "used": used,
        "limit": limit,
        "remaining": remaining,
        "percent": round(percent, 2),

        "upload_human": format_bytes(upload),
        "download_human": format_bytes(download),
        "used_human": format_bytes(used),
        "limit_human": format_bytes(limit),
        "remaining_human": format_bytes(
            remaining
        ),
    }


# ============================================================
# HAPP HEADERS
# ============================================================

def subscription_header(user):
    return (
        f"upload={user['upload']};"
        f" download={user['download']};"
        f" total={user['traffic_limit']};"
        f" expire={user['expire']}"
    )


# ============================================================
# PYDANTIC MODELS
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
        "success": True,
        "service": "ixxy VPN LAB",
        "version": "2.0",
        "status": "running",
    }


@app.get("/health")
def health():
    return {
        "success": True,
        "status": "ok",
        "time": now(),
    }


# ============================================================
# CREATE USER
# ============================================================

@app.post("/api/user/create")
def api_create_user(
    request: CreateUserRequest
):
    user = get_or_create_user(
        request.telegram_id
    )

    if not user:
        raise HTTPException(
            status_code=500,
            detail="Failed to create user",
        )

    token = user["token"]

    return {
        "success": True,
        "user": user,
        "subscription_url": (
            f"{PUBLIC_URL}/sub/{token}"
        ),
        "traffic": get_traffic(user),
        "devices": get_devices(
            user["id"]
        ),
        "device_count": len(
            get_devices(user["id"])
        ),
    }


# ============================================================
# GET USER
# ============================================================

@app.get("/api/user/{telegram_id}")
def api_get_user(
    telegram_id: int
):
    user = get_user_by_telegram(
        telegram_id
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="User not found",
        )

    user = row_to_dict(user)

    token = user["token"]

    devices = get_devices(
        user["id"]
    )

    return {
        "success": True,
        "user": user,
        "subscription_url": (
            f"{PUBLIC_URL}/sub/{token}"
        ),
        "traffic": get_traffic(user),
        "devices": devices,
        "device_count": len(devices),
    }


# ============================================================
# GET USER BY TOKEN
# ============================================================

@app.get("/api/token/{token}")
def api_get_token(token: str):
    user = get_user_by_token(token)

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Token not found",
        )

    user = row_to_dict(user)

    devices = get_devices(
        user["id"]
    )

    return {
        "success": True,
        "user": user,
        "traffic": get_traffic(user),
        "devices": devices,
        "device_count": len(devices),
    }


# ============================================================
# REGISTER DEVICE
# ============================================================

@app.post("/api/device/register")
def api_register_device(
    request: RegisterDeviceRequest
):
    user = get_user_by_token(
        request.token
    )

    if not user:
        raise HTTPException(
            status_code=404,
            detail="Invalid token",
        )

    result = register_device(
        user_id=user["id"],
        device_id=request.device_id.strip(),
        device_name=request.device_name.strip(),
        platform=request.platform.strip(),
    )

    if not result["success"]:

        if result.get("error") == "device_limit":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "device_limit",
                    "message": "Device limit reached",
                    "device_limit": result[
                        "device_limit"
                    ],
                    "device_count": result[
                        "device_count"
                    ],
                },
            )

        raise HTTPException(
            status_code=400,
            detail=result,
        )

    devices = get_devices(
        user["id"]
    )

    return {
        "success": True,
        "message": (
            "Device registered"
        ),
        "device": result["device"],
        "devices": devices,
        "device_count": len(devices),
        "device_limit": user[
            "device_limit"
        ],
    }


# ============================================================
# DELETE DEVICE
# ============================================================

@app.delete(
    "/api/device/{token}/{device_id}"
)
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
        user["id"],
        device_id,
    )

    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Device not found",
        )

    devices = get_devices(
        user["id"]
    )

    return {
        "success": True,
        "message": "Device deleted",
        "devices": devices,
        "device_count": len(devices),
        "device_limit": user[
            "device_limit"
        ],
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

    return get_traffic(user)


# ============================================================
# SERVERS
# ============================================================

@app.get("/api/servers")
def api_servers():
    result = []

    for index, link in enumerate(
        VLESS_SERVERS,
        start=1
    ):
        name = (
            link.split("#", 1)[1]
            if "#" in link
            else f"Server {index}"
        )

        result.append(
            {
                "id": index,
                "name": name,
                "status": "configured",
                "link": link,
            }
        )

    return {
        "success": True,
        "count": len(result),
        "servers": result,
    }


# ============================================================
# SUBSCRIPTION
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

    if current >= user["expire"]:

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
            "#Подписка неактивна"
        )

        return PlainTextResponse(
            content=expired_link,
            headers={
                "subscription-userinfo": (
                    "upload=0; "
                    "download=0; "
                    f"total={user['traffic_limit']}; "
                    f"expire={user['expire']}"
                ),
                "profile-title": "ixxy VPN LAB",
                "profile-update-interval": "60",
                "cache-control": "no-cache",
            },
        )

    # --------------------------------------------------------
    # ACTIVE
    # --------------------------------------------------------

    content = "\n".join(
        VLESS_SERVERS
    )

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
                "no-cache",
        },
    )


# ============================================================
# STATS
# ============================================================

@app.get("/api/stats")
def api_stats():

    conn = db()

    users = conn.execute(
        "SELECT COUNT(*) FROM users"
    ).fetchone()[0]

    devices = conn.execute(
        """
        SELECT COUNT(*)
        FROM devices
        WHERE active = 1
        """
    ).fetchone()[0]

    conn.close()

    return {
        "success": True,
        "users": users,
        "active_devices": devices,
        "servers": len(
            VLESS_SERVERS
        ),
    }


# ============================================================
# RUN
# ============================================================

if __name__ == "__main__":
    import uvicorn

    port = int(
        os.getenv("PORT", "8000")
    )

    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=port,
    )