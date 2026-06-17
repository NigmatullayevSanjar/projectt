import os
import asyncpg

# ======================================================
#  DATABASE SOZLAMALARI (Render Env & Local moslashuv)
# ======================================================
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:5056@localhost:5432/kafel_db"
)
# ======================================================

pool: asyncpg.Pool = None


async def init_db():
    global pool
    pool = await asyncpg.create_pool(dsn=DATABASE_URL)
    
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                telegram_id   BIGINT PRIMARY KEY,
                first_name    TEXT NOT NULL,
                last_name     TEXT NOT NULL,
                phone         TEXT NOT NULL,
                username      TEXT DEFAULT '—',
                registered_at TIMESTAMP DEFAULT NOW()
            );
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS kafels (
                id          SERIAL PRIMARY KEY,
                name        TEXT NOT NULL,
                category    TEXT NOT NULL,  -- Ceramika, Shisha, Toshli va h.k.
                price       BIGINT NOT NULL,
                description TEXT DEFAULT '',
                photo_id    TEXT DEFAULT NULL,
                added_at    TIMESTAMP DEFAULT NOW()
            );
        """)
    print("✅ PostgreSQL ulanishi muvaffaqiyatli yakunlandi!")


# ===== USERS =====
async def db_add_user(uid, first_name, last_name, phone, username):
    async with pool.acquire() as conn:
        await conn.execute("""
            INSERT INTO users (telegram_id, first_name, last_name, phone, username)
            VALUES ($1,$2,$3,$4,$5)
            ON CONFLICT (telegram_id) DO UPDATE
            SET first_name=$2, last_name=$3, phone=$4, username=$5
        """, uid, first_name, last_name, phone, username)

async def db_get_user(uid):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM users WHERE telegram_id=$1", uid)

async def db_is_registered(uid):
    async with pool.acquire() as conn:
        row = await conn.fetchrow("SELECT 1 FROM users WHERE telegram_id=$1", uid)
        return row is not None

async def db_get_all_users():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM users ORDER BY registered_at DESC")

async def db_count_users():
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM users")


# ===== KAFELS =====
async def db_add_kafel(name, category, price, description, photo_id):
    async with pool.acquire() as conn:
        return await conn.fetchrow("""
            INSERT INTO kafels (name, category, price, description, photo_id)
            VALUES ($1,$2,$3,$4,$5) RETURNING *
        """, name, category, price, description, photo_id)

async def db_get_kafels():
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM kafels ORDER BY id")

async def db_get_kafels_by_category(category):
    async with pool.acquire() as conn:
        return await conn.fetch("SELECT * FROM kafels WHERE category=$1 ORDER BY id", category)

async def db_get_kafel(kid):
    async with pool.acquire() as conn:
        return await conn.fetchrow("SELECT * FROM kafels WHERE id=$1", kid)

async def db_delete_kafel(kid):
    async with pool.acquire() as conn:
        result = await conn.execute("DELETE FROM kafels WHERE id=$1", kid)
        return result != "DELETE 0"

async def db_count_kafels():
    async with pool.acquire() as conn:
        return await conn.fetchval("SELECT COUNT(*) FROM kafels")


# ===== HELPER =====
def kafel_card(k):
    return (
        f"🏷 <b>{k['name']}</b>\n"
        f"🗂 Kategoriya: <code>{k['category']}</code>\n"
        f"💰 Narxi: <b>{k['price']:,} so'm</b>\n"
        f"📝 Tavsif: {k['description'] or '—'}"
    )