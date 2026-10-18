"""
INNOVA Database Layer (SQLite)
Manages persistence, schema migrations, foreign keys, and seed data.
"""

import sqlite3
import os
import json
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta

DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
DB_PATH = os.path.join(DB_DIR, "innova.db")
CATALOG_DATA_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "catalog-data.js")


def get_db():
    """Returns a configured SQLite connection with foreign keys and Row factory."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=20.0)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> tuple[str, str]:
    """Hashes a password using PBKDF2-HMAC-SHA256 with 600,000 iterations."""
    salt = secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
    return salt.hex(), key.hex()


def verify_password(password: str, salt_hex: str, key_hex: str) -> bool:
    """Verifies a password against the stored salt and hash."""
    try:
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 600000)
        return hmac.compare_digest(key, expected_key)
    except Exception:
        return False


def init_db():
    """Initializes database schema and runs migrations if needed."""
    conn = get_db()
    with conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                role TEXT DEFAULT 'admin',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS sessions (
                token TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP NOT NULL,
                ip_address TEXT,
                user_agent TEXT
            );

            CREATE TABLE IF NOT EXISTS login_attempts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                identifier TEXT NOT NULL,
                attempt_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                success INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                description TEXT,
                image_url TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                price REAL NOT NULL CHECK(price >= 0),
                promo_price REAL CHECK(promo_price IS NULL OR promo_price >= 0),
                stock INTEGER NOT NULL DEFAULT 0 CHECK(stock >= 0),
                sku TEXT,
                short_description TEXT,
                full_description TEXT,
                status TEXT DEFAULT 'active' CHECK(status IN ('active', 'inactive', 'draft')),
                featured INTEGER DEFAULT 0,
                specs_json TEXT DEFAULT '[]',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS product_images (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                image_url TEXT NOT NULL,
                is_primary INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                user_id INTEGER REFERENCES users(id) ON DELETE SET NULL,
                previous_stock INTEGER NOT NULL,
                new_stock INTEGER NOT NULL,
                delta INTEGER NOT NULL,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS promotions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                description TEXT,
                discount_type TEXT NOT NULL CHECK(discount_type IN ('percent', 'fixed')),
                discount_value REAL NOT NULL CHECK(discount_value > 0),
                target_type TEXT NOT NULL CHECK(target_type IN ('all', 'category', 'product')),
                target_id TEXT,
                starts_at TIMESTAMP NOT NULL,
                ends_at TIMESTAMP NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS customer_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                event_type TEXT NOT NULL,
                target_id TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS customer_favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                product_id TEXT NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, product_id)
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                type TEXT DEFAULT 'system',
                target_type TEXT DEFAULT 'all',
                target_id TEXT,
                link_url TEXT,
                created_by INTEGER REFERENCES users(id),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS user_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                notification_id INTEGER NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                is_read INTEGER DEFAULT 0,
                read_at TIMESTAMP,
                is_deleted INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(notification_id, user_id)
            );

            CREATE TABLE IF NOT EXISTS password_resets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                token TEXT UNIQUE NOT NULL,
                expires_at TIMESTAMP NOT NULL,
                used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_products_category ON products(category_id);
            CREATE INDEX IF NOT EXISTS idx_products_status ON products(status);
            CREATE INDEX IF NOT EXISTS idx_products_featured ON products(featured);
            CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
            CREATE INDEX IF NOT EXISTS idx_login_attempts ON login_attempts(ip, identifier, attempt_time);
            CREATE INDEX IF NOT EXISTS idx_promotions_dates ON promotions(starts_at, ends_at, is_active);
            CREATE INDEX IF NOT EXISTS idx_activity_user ON customer_activity(user_id, created_at);
            CREATE INDEX IF NOT EXISTS idx_favorites_user ON customer_favorites(user_id);
            CREATE INDEX IF NOT EXISTS idx_user_notif ON user_notifications(user_id, is_read, is_deleted);
            CREATE INDEX IF NOT EXISTS idx_password_resets_token ON password_resets(token);
        """)

    # Run safe migrations for newly added columns
    migrate_columns(conn)

    # Seed initial admin from environment variables if provided
    seed_admin_from_env(conn)

    # Seed default settings if missing
    seed_settings(conn)

    # Seed catalog if empty
    seed_catalog_if_empty(conn)

    conn.close()


def migrate_columns(conn):
    """Adds missing columns dynamically to existing database installations."""
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(users)")
    cols = {row["name"] for row in cur.fetchall()}
    with conn:
        if "full_name" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN full_name TEXT")
        if "phone" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN phone TEXT")
        if "notification_prefs_json" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN notification_prefs_json TEXT DEFAULT '{\"promotions\":true,\"new_products\":true,\"stock_alerts\":true,\"activity\":true}'")


def seed_admin_from_env(conn):
    """Provisions admin from private environment variables if configured and no admin exists."""
    admin_user = os.environ.get("ADMIN_USERNAME")
    admin_pass = os.environ.get("ADMIN_PASSWORD")
    admin_email = os.environ.get("ADMIN_EMAIL", "admin@innova.com")

    if not admin_user or not admin_pass:
        return

    cur = conn.cursor()
    cur.execute("SELECT id FROM users WHERE username = ? OR email = ?", (admin_user, admin_email))
    if cur.fetchone():
        return

    salt_hex, key_hex = hash_password(admin_pass)
    with conn:
        conn.execute("""
            INSERT INTO users (username, email, password_hash, salt, role, full_name)
            VALUES (?, ?, ?, ?, 'admin', 'Administrador Principal')
        """, (admin_user, admin_email, key_hex, salt_hex))
    print(f"[DB] Initial admin account '{admin_user}' provisioned securely from environment.")


def seed_settings(conn):
    """Seeds default store configuration if not present."""
    default_settings = {
        "store_name": "INNOVA",
        "store_tagline": "Tecnología, con intención",
        "whatsapp_url": "https://wa.link/xdirph",
        "whatsapp_phone": "+57 300 000 0000",
        "contact_email": "contacto@innova.com",
        "currency_code": "COP",
        "currency_symbol": "$",
        "low_stock_threshold": "5",
        "announcement": "Precios e inventario administrados en tiempo real."
    }
    with conn:
        for key, val in default_settings.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)",
                (key, val)
            )


DEFAULT_PRODUCTS = [
    {
        "id": "smartphone-pro",
        "name": "Smartphone Pro",
        "category": "Celulares",
        "price": 1299,
        "description": "Potencia y fotografía avanzada en un diseño refinado.",
        "details": "Un teléfono de alto rendimiento con pantalla inmersiva, un sistema de cámaras versátil y una batería pensada para acompañarte durante todo el día.",
        "image": "https://images.unsplash.com/photo-1592899677977-9c10ca588bbd?auto=format&fit=crop&w=900&q=80",
        "featured": True,
        "specs": ["Pantalla de alta resolución", "Sistema de cámaras avanzado", "Carga rápida"]
    },
    {
        "id": "smartphone-essential",
        "name": "Smartphone Essential",
        "category": "Celulares",
        "price": 749,
        "description": "Lo esencial, con una experiencia fluida y confiable.",
        "details": "Una opción equilibrada para conectar, crear y disfrutar de tus aplicaciones favoritas con una experiencia cómoda y sencilla.",
        "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?auto=format&fit=crop&w=900&q=80",
        "featured": False,
        "specs": ["Pantalla de gran formato", "Almacenamiento amplio", "Diseño ligero"]
    },
    {
        "id": "smartphone-compact",
        "name": "Smartphone Compact",
        "category": "Celulares",
        "price": 899,
        "description": "Un formato cómodo, con todo lo que necesitas.",
        "details": "Rendimiento equilibrado en un formato compacto y fácil de llevar, sin renunciar a una experiencia de uso completa.",
        "image": "https://images.unsplash.com/photo-1592750475338-74b7b21085ab?auto=format&fit=crop&w=900&q=80",
        "featured": False,
        "specs": ["Formato compacto", "Cámara de alta definición", "Conectividad actual"]
    },
    {
        "id": "auriculares-studio",
        "name": "Auriculares Studio",
        "category": "Audio",
        "price": 249,
        "description": "Sonido envolvente y comodidad para todo el día.",
        "details": "Escucha cada detalle con un diseño acolchado y liviano, pensado para largas sesiones de música, llamadas o concentración.",
        "image": "https://images.unsplash.com/photo-1546435770-a3e426bf472b?auto=format&fit=crop&w=900&q=80",
        "featured": True,
        "specs": ["Diseño circumaural", "Controles integrados", "Ajuste acolchado"]
    },
    {
        "id": "auriculares-in-ear",
        "name": "Auriculares In‑Ear",
        "category": "Audio",
        "price": 119,
        "description": "Libertad inalámbrica en un diseño discreto.",
        "details": "Auriculares compactos para escuchar música y atender llamadas con comodidad, en casa o mientras estás en movimiento.",
        "image": "https://images.unsplash.com/photo-1606220945770-b5b6c2c55bf1?auto=format&fit=crop&w=900&q=80",
        "featured": False,
        "specs": ["Estuche de carga", "Conexión inalámbrica", "Ajuste ligero"]
    },
    {
        "id": "reloj-smart",
        "name": "Reloj Smart",
        "category": "Wearables",
        "price": 329,
        "description": "Información útil y diseño cuidado en tu muñeca.",
        "details": "Consulta notificaciones, actividad y datos cotidianos de un vistazo, con una interfaz clara y un diseño versátil.",
        "image": "https://images.unsplash.com/photo-1523275335684-37898b6baf30?auto=format&fit=crop&w=900&q=80",
        "featured": True,
        "specs": ["Pantalla táctil", "Seguimiento de actividad", "Correa intercambiable"]
    },
    {
        "id": "parlante-portatil",
        "name": "Parlante Portátil",
        "category": "Accesorios",
        "price": 159,
        "description": "Tu música favorita, lista para acompañarte.",
        "details": "Un parlante compacto y fácil de llevar, pensado para disfrutar sonido nítido en tus espacios favoritos.",
        "image": "https://images.unsplash.com/photo-1608043152269-423dbba4e7e1?auto=format&fit=crop&w=900&q=80",
        "featured": False,
        "specs": ["Diseño portátil", "Conexión inalámbrica", "Controles sencillos"]
    },
    {
        "id": "cargador-compacto",
        "name": "Cargador Compacto",
        "category": "Accesorios",
        "price": 49,
        "description": "Carga práctica en casa, en la oficina o de viaje.",
        "details": "Una solución compacta para mantener tus dispositivos listos, con un formato práctico para llevar contigo.",
        "image": "https://images.unsplash.com/photo-1583863788434-e58a36330cf0?auto=format&fit=crop&w=900&q=80",
        "featured": False,
        "specs": ["Formato compacto", "Compatible con varios dispositivos", "Fácil de transportar"]
    }
]


def seed_catalog_if_empty(conn):
    """Populates initial products and categories so no existing catalog data is lost."""
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) as count FROM products")
    if cur.fetchone()["count"] > 0:
        return  # Already populated

    products = DEFAULT_PRODUCTS

    try:
        with conn:
            # Insert categories
            categories_map = {}
            for p in products:
                cat_name = p.get("category", "General")
                if cat_name not in categories_map:
                    slug = cat_name.lower().replace(" ", "-").replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
                    cur.execute(
                        "INSERT OR IGNORE INTO categories (name, slug, description) VALUES (?, ?, ?)",
                        (cat_name, slug, f"Categoría de {cat_name}")
                    )
                    cur.execute("SELECT id FROM categories WHERE name = ?", (cat_name,))
                    cat_row = cur.fetchone()
                    categories_map[cat_name] = cat_row["id"]

            # Insert products
            for p in products:
                cat_id = categories_map.get(p.get("category"))
                prod_id = p.get("id")
                name = p.get("name")
                slug = prod_id
                price = float(p.get("price", 0))
                short_desc = p.get("description", "")
                full_desc = p.get("details", "")
                featured = 1 if p.get("featured") else 0
                specs = json.dumps(p.get("specs", []), ensure_ascii=False)
                stock = 15  # Healthy default stock for demo catalog

                conn.execute("""
                    INSERT OR IGNORE INTO products (
                        id, name, slug, category_id, price, stock, sku,
                        short_description, full_description, status, featured, specs_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?)
                """, (
                    prod_id, name, slug, cat_id, price, stock, f"SKU-{prod_id.upper()}",
                    short_desc, full_desc, featured, specs
                ))

                # Insert primary image
                image_url = p.get("image")
                if image_url:
                    conn.execute("""
                        INSERT OR IGNORE INTO product_images (product_id, image_url, is_primary, sort_order)
                        VALUES (?, ?, 1, 0)
                    """, (prod_id, image_url))

                # Record initial stock movement
                conn.execute("""
                    INSERT INTO stock_movements (product_id, user_id, previous_stock, new_stock, delta, reason)
                    VALUES (?, NULL, 0, ?, ?, 'Carga inicial del catálogo')
                """, (prod_id, stock, stock))

        print(f"[DB] Initialized database with {len(products)} products and categories.")
    except Exception as e:
        print(f"[DB] Error during seeding: {e}")


if __name__ == "__main__":
    init_db()
    print("[DB] Database initialized successfully at:", DB_PATH)
