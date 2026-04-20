import aiosqlite
import os

DB_PATH = "database.db"

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # Users Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                total_earned INTEGER DEFAULT 0,
                last_boost_reward DATE
            )
        ''')
        
        # Submissions Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS submissions (
                submission_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                type TEXT, -- 'review', 'update', 'video', 'verification'
                status TEXT, -- 'pending', 'approved', 'rejected'
                location_id TEXT,
                location_name TEXT,
                country TEXT,
                accessibility INTEGER,
                quality INTEGER,
                coordinates TEXT,
                name_change TEXT,
                map_category TEXT,
                content TEXT,
                video_link TEXT,
                submitted_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Add columns if they don't exist (Migration)
        columns_to_add = [
            ("location_name", "TEXT"),
            ("country", "TEXT"),
            ("accessibility", "INTEGER"),
            ("quality", "INTEGER"),
            ("coordinates", "TEXT"),
            ("name_change", "TEXT"),
            ("map_category", "TEXT"),
            ("last_daily", "TEXT"),
            ("last_message_reward", "TEXT"),
            ("submission_message_link", "TEXT"),
            ("admin_grid_message_id", "TEXT"),
            ("admin_button_message_id", "TEXT"),
            ("video_link", "TEXT")
        ]
        
        for col_name, col_type in columns_to_add:
            try:
                await db.execute(f"ALTER TABLE submissions ADD COLUMN {col_name} {col_type}")
            except:
                pass
            try:
                await db.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except:
                pass
        
        # Shop Items Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_items (
                item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                price INTEGER,
                stock INTEGER DEFAULT -1, -- -1 for infinite
                description TEXT,
                is_physical BOOLEAN DEFAULT 0
            )
        ''')
        
        # Inventory Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS inventory (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                item_id INTEGER,
                purchased_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(item_id) REFERENCES shop_items(item_id)
            )
        ''')
        
        # Transactions Log
        await db.execute('''
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                type TEXT, -- 'earn', 'spend', 'admin'
                reason TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Settings Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')
        
        # Activity Logs Table
        await db.execute('''
            CREATE TABLE IF NOT EXISTS activity_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                log_type TEXT,
                title TEXT,
                description TEXT,
                color INTEGER,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Cleanup Level/XP (Migration) - Drop columns if they exist
        # SQLite 3.35.0+ supports DROP COLUMN
        for col in ["level", "xp"]:
            try:
                await db.execute(f"ALTER TABLE users DROP COLUMN {col}")
            except:
                pass

        await db.commit()

async def get_setting(key: str, default: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else default

async def set_setting(key: str, value: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        await db.commit()

async def get_user_balance(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            if row:
                return row[0]
            else:
                await db.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
                await db.commit()
                return 0

async def get_user_stats(user_id: int):
    """Returns a dictionary of user stats including balance and approved submissions."""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT balance, total_earned FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user_row = await cursor.fetchone()
        
        async with db.execute("SELECT COUNT(*) FROM submissions WHERE user_id = ? AND status = 'approved'", (user_id,)) as cursor:
            subs_row = await cursor.fetchone()
            
        if not user_row:
            return None
            
        return {
            "balance": user_row[0],
            "total_earned": user_row[1],
            "submissions": subs_row[0] if subs_row else 0
        }

async def update_user_balance(user_id: int, amount: int, reason: str = "Admin adjustment"):
    current_balance = await get_user_balance(user_id) or 0
    new_balance = current_balance + amount
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance = ?, total_earned = total_earned + ? WHERE user_id = ?", 
                         (new_balance, max(0, amount), user_id))
        await db.execute("INSERT INTO transactions (user_id, amount, type, reason) VALUES (?, ?, ?, ?)", 
                         (user_id, amount, 'earn' if amount > 0 else 'spend', reason))
        await db.commit()
    return new_balance

async def check_duplicate_submission(location_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT submission_id FROM submissions WHERE location_id = ? AND status != 'rejected'", (location_id,)) as cursor:
            return await cursor.fetchone() is not None

async def get_submission(submission_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM submissions WHERE submission_id = ?", (submission_id,)) as cursor:
            return await cursor.fetchone()
