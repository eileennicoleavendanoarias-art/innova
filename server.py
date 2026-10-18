"""
INNOVA Full-Stack E-Commerce & Management Server
Multi-threaded HTTP server with RESTful API, Customer Accounts & Personalization,
Role-Based Authorization (Cliente vs Admin), Persistent SQLite Storage,
Activity Logging, Smart Recommendations, and Internal Notifications System.
"""

import sys
import os
import json
import sqlite3
import secrets
import mimetypes
import uuid
import re
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from http.cookies import SimpleCookie

# Setup directory paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
ADMIN_DIR = os.path.join(BASE_DIR, "admin")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(ADMIN_DIR, exist_ok=True)

sys.path.insert(0, BASE_DIR)
import db

# Initialize database on module load
db.init_db()


class InnovaRequestHandler(SimpleHTTPRequestHandler):
    """Handles static files, uploads, authentication, customer portal, and REST API."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=BASE_DIR, **kwargs)

    # ---------------------------------------------------------
    # Helper Utilities
    # ---------------------------------------------------------
    def send_json(self, data, status=200, headers=None):
        payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("X-XSS-Protection", "1; mode=block")
        if headers:
            for k, v in headers.items():
                self.send_header(k, v)
        self.end_headers()
        self.wfile.write(payload)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message, "status": status}, status=status)

    def get_client_ip(self):
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0]

    def read_json_body(self):
        try:
            content_length = int(self.headers.get("Content-Length", 0))
            if content_length <= 0:
                return {}
            body = self.rfile.read(content_length).decode("utf-8")
            return json.loads(body)
        except Exception:
            return None

    def get_cookie(self, name):
        cookie_header = self.headers.get("Cookie")
        if not cookie_header:
            return None
        cookie = SimpleCookie()
        try:
            cookie.load(cookie_header)
            if name in cookie:
                return cookie[name].value
        except Exception:
            return None
        return None

    def get_authenticated_user(self):
        """Validates session token from cookie and returns user record or None."""
        token = self.get_cookie("innova_session")
        if not token:
            auth_header = self.headers.get("Authorization")
            if auth_header and auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()

        if not token:
            return None

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT u.id, u.username, u.email, u.role, u.full_name, u.phone,
                   u.notification_prefs_json, u.created_at, s.expires_at
            FROM sessions s
            JOIN users u ON s.user_id = u.id
            WHERE s.token = ? AND datetime(s.expires_at) > datetime('now')
        """, (token,))
        user = cur.fetchone()
        conn.close()
        return user

    def require_auth(self):
        """Returns authenticated user or sends 401 and returns None."""
        user = self.get_authenticated_user()
        if not user:
            self.send_error_json("No autorizado. Inicie sesión para acceder a esta función.", 401)
            return None
        return user

    def require_admin(self):
        """Returns authenticated admin user or sends 401/403 and returns None."""
        user = self.get_authenticated_user()
        if not user:
            self.send_error_json("No autorizado. Inicie sesión para acceder a esta función.", 401)
            return None
        if user["role"] != "admin":
            self.send_error_json("Acceso denegado. Se requieren permisos de administrador.", 403)
            return None
        return user

    # ---------------------------------------------------------
    # Rate Limiting for Authentication
    # ---------------------------------------------------------
    def is_rate_limited(self, ip, identifier):
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT COUNT(*) as failed_count
            FROM login_attempts
            WHERE (ip = ? OR identifier = ?)
              AND success = 0
              AND datetime(attempt_time) > datetime('now', '-15 minutes')
        """, (ip, identifier))
        count = cur.fetchone()["failed_count"]
        conn.close()
        return count >= 5

    def record_login_attempt(self, ip, identifier, success):
        conn = db.get_db()
        with conn:
            conn.execute("""
                INSERT INTO login_attempts (ip, identifier, success)
                VALUES (?, ?, ?)
            """, (ip, identifier, 1 if success else 0))
        conn.close()

    # ---------------------------------------------------------
    # HTTP Method Handlers
    # ---------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Allow", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, PATCH, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Route /admin to /admin/index.html
        if path == "/admin" or path == "/admin/":
            self.path = "/admin/index.html"
            return super().do_GET()

        # Handle API routes
        if path.startswith("/api/"):
            return self.handle_api_get(path, query)

        # Default static file handler
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/"):
            return self.handle_api_post(path, query)

        self.send_error_json("Ruta POST no encontrada", 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/"):
            return self.handle_api_put(path, query)

        self.send_error_json("Ruta PUT no encontrada", 404)

    def do_PATCH(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/"):
            return self.handle_api_patch(path, query)

        self.send_error_json("Ruta PATCH no encontrada", 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path.startswith("/api/"):
            return self.handle_api_delete(path, query)

        self.send_error_json("Ruta DELETE no encontrada", 404)

    # ---------------------------------------------------------
    # API GET Router
    # ---------------------------------------------------------
    def handle_api_get(self, path, query):
        if path == "/api/auth/me":
            return self.api_auth_me()

        # Customer Portal Endpoints
        if path == "/api/customer/profile":
            return self.api_customer_get_profile()

        if path == "/api/customer/activity":
            return self.api_customer_get_activity(query)

        if path == "/api/customer/favorites":
            return self.api_customer_get_favorites()

        if path == "/api/customer/recommendations":
            return self.api_customer_get_recommendations()

        if path == "/api/customer/notifications":
            return self.api_customer_get_notifications()

        # Admin & Public Endpoints
        if path == "/api/dashboard":
            return self.api_dashboard()

        if path == "/api/admin/notifications":
            return self.api_admin_get_notifications(query)

        if path == "/api/products":
            return self.api_get_products(query)

        if re.match(r"^/api/products/[^/]+$", path):
            prod_id = path.split("/")[-1]
            return self.api_get_product_detail(prod_id)

        if path == "/api/inventory":
            return self.api_get_inventory(query)

        if path == "/api/inventory/movements":
            return self.api_get_stock_movements(query)

        if path == "/api/promotions":
            return self.api_get_promotions(query)

        if path == "/api/categories":
            return self.api_get_categories()

        if path == "/api/settings":
            return self.api_get_settings()

        self.send_error_json("Endpoint no encontrado", 404)

    # ---------------------------------------------------------
    # API POST Router
    # ---------------------------------------------------------
    def handle_api_post(self, path, query):
        if path == "/api/auth/register":
            return self.api_auth_register()

        if path == "/api/auth/login":
            return self.api_auth_login()

        if path == "/api/auth/logout":
            return self.api_auth_logout()

        if path == "/api/auth/password-reset-request":
            return self.api_auth_password_reset_request()

        if path == "/api/auth/password-reset-confirm":
            return self.api_auth_password_reset_confirm()

        # Customer Operations
        if path == "/api/customer/change-password":
            return self.api_customer_change_password()

        if path == "/api/customer/activity":
            return self.api_customer_record_activity()

        if path == "/api/customer/favorites":
            return self.api_customer_toggle_favorite()

        if path == "/api/customer/notifications/mark-all-read":
            return self.api_customer_mark_all_notifications_read()

        # Admin Operations
        if path == "/api/upload":
            return self.api_upload()

        if path == "/api/products":
            return self.api_create_product()

        m_dup = re.match(r"^/api/products/([^/]+)/duplicate$", path)
        if m_dup:
            return self.api_admin_duplicate_product(m_dup.group(1))

        if path == "/api/inventory/adjust":
            return self.api_adjust_inventory()

        if path == "/api/promotions":
            return self.api_create_promotion()

        if path == "/api/categories":
            return self.api_create_category()

        if path == "/api/admin/notifications":
            return self.api_admin_send_notification()

        self.send_error_json("Endpoint no encontrado", 404)

    # ---------------------------------------------------------
    # API PUT Router
    # ---------------------------------------------------------
    def handle_api_put(self, path, query):
        if path == "/api/customer/profile":
            return self.api_customer_update_profile()

        if re.match(r"^/api/products/[^/]+$", path):
            prod_id = path.split("/")[-1]
            return self.api_update_product(prod_id)

        if re.match(r"^/api/promotions/\d+$", path):
            promo_id = int(path.split("/")[-1])
            return self.api_update_promotion(promo_id)

        if re.match(r"^/api/categories/\d+$", path):
            cat_id = int(path.split("/")[-1])
            return self.api_update_category(cat_id)

        if path == "/api/settings":
            return self.api_update_settings()

        self.send_error_json("Ruta PUT no encontrada", 404)

    # ---------------------------------------------------------
    # API PATCH Router
    # ---------------------------------------------------------
    def handle_api_patch(self, path, query):
        m_read = re.match(r"^/api/customer/notifications/(\d+)/read$", path)
        if m_read:
            return self.api_customer_read_notification(int(m_read.group(1)))

        m_status = re.match(r"^/api/products/([^/]+)/status$", path)
        if m_status:
            return self.api_patch_product_status(m_status.group(1))

        m_feat = re.match(r"^/api/products/([^/]+)/featured$", path)
        if m_feat:
            return self.api_patch_product_featured(m_feat.group(1))

        m_promo = re.match(r"^/api/promotions/(\d+)/status$", path)
        if m_promo:
            return self.api_patch_promotion_status(int(m_promo.group(1)))

        self.send_error_json("Endpoint no encontrado", 404)

    # ---------------------------------------------------------
    # API DELETE Router
    # ---------------------------------------------------------
    def handle_api_delete(self, path, query):
        if path == "/api/customer/activity":
            return self.api_customer_clear_activity()

        if path == "/api/customer/account":
            return self.api_customer_delete_account()

        m_fav = re.match(r"^/api/customer/favorites/([^/]+)$", path)
        if m_fav:
            return self.api_customer_remove_favorite(m_fav.group(1))

        m_notif = re.match(r"^/api/customer/notifications/(\d+)$", path)
        if m_notif:
            return self.api_customer_delete_notification(int(m_notif.group(1)))

        m_admin_notif = re.match(r"^/api/admin/notifications/(\d+)$", path)
        if m_admin_notif:
            return self.api_admin_delete_notification(int(m_admin_notif.group(1)))

        if re.match(r"^/api/products/[^/]+$", path):
            prod_id = path.split("/")[-1]
            return self.api_delete_product(prod_id)

        if re.match(r"^/api/promotions/\d+$", path):
            promo_id = int(path.split("/")[-1])
            return self.api_delete_promotion(promo_id)

        if re.match(r"^/api/categories/\d+$", path):
            cat_id = int(path.split("/")[-1])
            return self.api_delete_category(cat_id)

        self.send_error_json("Endpoint no encontrado", 404)

    # =========================================================
    # AUTHENTICATION & REGISTRATION ENDPOINTS
    # =========================================================
    def api_auth_register(self):
        """Registers a new customer account. STRICTLY forces role = 'cliente'."""
        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        full_name = str(body.get("full_name", "")).strip()
        email = str(body.get("email", "")).strip().lower()
        password = str(body.get("password", ""))

        if not full_name:
            return self.send_error_json("El nombre completo es obligatorio", 400)

        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email):
            return self.send_error_json("El correo electrónico no tiene un formato válido", 400)

        if len(password) < 8:
            return self.send_error_json("La contraseña debe tener al menos 8 caracteres", 400)

        conn = db.get_db()
        cur = conn.cursor()

        # Check existing email
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cur.fetchone():
            conn.close()
            return self.send_error_json("Ya existe una cuenta registrada con este correo electrónico", 409)

        # Generate username based on email local-part
        base_user = re.sub(r"[^a-zA-Z0-9_]", "", email.split("@")[0])[:20] or "cliente"
        username = base_user
        idx = 1
        while True:
            cur.execute("SELECT id FROM users WHERE username = ?", (username,))
            if not cur.fetchone():
                break
            username = f"{base_user}{idx}"
            idx += 1

        salt_hex, key_hex = db.hash_password(password)

        notification_prefs = body.get("notification_prefs", {
            "promotions": True,
            "new_products": True,
            "stock_alerts": True,
            "activity": True
        })
        prefs_json = json.dumps(notification_prefs)

        with conn:
            cur.execute("""
                INSERT INTO users (username, email, password_hash, salt, role, full_name, notification_prefs_json)
                VALUES (?, ?, ?, ?, 'cliente', ?, ?)
            """, (username, email, key_hex, salt_hex, full_name, prefs_json))
            user_id = cur.lastrowid

            # Create welcome notification
            cur.execute("""
                INSERT INTO notifications (title, message, type, target_type, link_url)
                VALUES ('¡Bienvenido a INNOVA!', 'Tu cuenta ha sido creada exitosamente. Explora nuestro catálogo y personaliza tus preferencias.', 'system', 'user', '#catalogo')
            """)
            notif_id = cur.lastrowid
            cur.execute("""
                INSERT INTO user_notifications (notification_id, user_id)
                VALUES (?, ?)
            """, (notif_id, user_id))

        # Create session
        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        ip = self.get_client_ip()
        user_agent = self.headers.get("User-Agent", "")[:255]

        with conn:
            conn.execute("""
                INSERT INTO sessions (token, user_id, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """, (token, user_id, expires_at, ip, user_agent))

        conn.close()

        cookie_val = f"innova_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={7*86400}"
        return self.send_json({
            "success": True,
            "user": {
                "id": user_id,
                "username": username,
                "email": email,
                "full_name": full_name,
                "role": "cliente",
                "notification_prefs": notification_prefs
            }
        }, status=201, headers={"Set-Cookie": cookie_val})

    def api_auth_login(self):
        """Unified login endpoint for both Cliente and Admin."""
        ip = self.get_client_ip()
        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        identifier = str(body.get("identifier", "")).strip()
        password = str(body.get("password", ""))

        if not identifier or not password:
            return self.send_error_json("Usuario y contraseña son requeridos", 400)

        if self.is_rate_limited(ip, identifier):
            return self.send_error_json(
                "Demasiados intentos de acceso fallidos. Por seguridad, espere 15 minutos.", 429
            )

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, username, email, password_hash, salt, role, full_name, notification_prefs_json
            FROM users
            WHERE username = ? OR email = ?
        """, (identifier, identifier))
        user = cur.fetchone()

        if not user or not db.verify_password(password, user["salt"], user["password_hash"]):
            self.record_login_attempt(ip, identifier, success=False)
            conn.close()
            return self.send_error_json("Credenciales incorrectas", 401)

        # Successful login
        self.record_login_attempt(ip, identifier, success=True)

        token = secrets.token_urlsafe(32)
        expires_at = (datetime.utcnow() + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        user_agent = self.headers.get("User-Agent", "")[:255]

        with conn:
            conn.execute("""
                INSERT INTO sessions (token, user_id, expires_at, ip_address, user_agent)
                VALUES (?, ?, ?, ?, ?)
            """, (token, user["id"], expires_at, ip, user_agent))
            conn.execute("UPDATE users SET last_login = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))

        conn.close()

        cookie_val = f"innova_session={token}; Path=/; HttpOnly; SameSite=Strict; Max-Age={7*86400}"
        prefs = {}
        try:
            if user["notification_prefs_json"]:
                prefs = json.loads(user["notification_prefs_json"])
        except Exception:
            pass

        return self.send_json(
            {
                "success": True,
                "role": user["role"],
                "user": {
                    "id": user["id"],
                    "username": user["username"],
                    "email": user["email"],
                    "full_name": user["full_name"] or user["username"],
                    "role": user["role"],
                    "notification_prefs": prefs
                }
            },
            headers={"Set-Cookie": cookie_val}
        )

    def api_auth_logout(self):
        token = self.get_cookie("innova_session")
        if token:
            conn = db.get_db()
            with conn:
                conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
            conn.close()

        cookie_clear = "innova_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return self.send_json({"success": True}, headers={"Set-Cookie": cookie_clear})

    def api_auth_me(self):
        user = self.get_authenticated_user()
        if not user:
            return self.send_error_json("No autenticado", 401)

        prefs = {}
        try:
            if user["notification_prefs_json"]:
                prefs = json.loads(user["notification_prefs_json"])
        except Exception:
            pass

        return self.send_json({
            "authenticated": True,
            "role": user["role"],
            "user": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"] or user["username"],
                "phone": user["phone"] or "",
                "role": user["role"],
                "created_at": user["created_at"],
                "notification_prefs": prefs
            }
        })

    def api_auth_password_reset_request(self):
        body = self.read_json_body()
        email = str(body.get("email", "")).strip().lower() if body else ""
        if not email:
            return self.send_error_json("El correo electrónico es requerido", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM users WHERE email = ?", (email,))
        user = cur.fetchone()

        token = secrets.token_urlsafe(24)
        if user:
            expires_at = (datetime.utcnow() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
            with conn:
                conn.execute("""
                    INSERT INTO password_resets (user_id, token, expires_at)
                    VALUES (?, ?, ?)
                """, (user["id"], token, expires_at))

        conn.close()
        # Always return a generic secure response to avoid user enumeration
        return self.send_json({
            "success": True,
            "message": "Si la dirección coincide con una cuenta registrada, se ha generado el código de recuperación.",
            "reset_token": token if user else None
        })

    def api_auth_password_reset_confirm(self):
        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        token = str(body.get("token", "")).strip()
        new_password = str(body.get("new_password", ""))

        if not token or len(new_password) < 8:
            return self.send_error_json("Token inválido o contraseña demasiado corta (mínimo 8 caracteres)", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, user_id, expires_at, used
            FROM password_resets
            WHERE token = ? AND used = 0 AND datetime(expires_at) > datetime('now')
        """, (token,))
        reset_entry = cur.fetchone()

        if not reset_entry:
            conn.close()
            return self.send_error_json("El código de recuperación es inválido o ha expirado.", 400)

        salt_hex, key_hex = db.hash_password(new_password)
        with conn:
            conn.execute("""
                UPDATE users SET password_hash = ?, salt = ? WHERE id = ?
            """, (key_hex, salt_hex, reset_entry["user_id"]))
            conn.execute("UPDATE password_resets SET used = 1 WHERE id = ?", (reset_entry["id"],))
            # Invalidate all existing sessions
            conn.execute("DELETE FROM sessions WHERE user_id = ?", (reset_entry["user_id"],))

        conn.close()
        return self.send_json({
            "success": True,
            "message": "Contraseña actualizada exitosamente. Ya puedes iniciar sesión con tu nueva contraseña."
        })

    # =========================================================
    # CUSTOMER PORTAL ENDPOINTS
    # =========================================================
    def api_customer_get_profile(self):
        user = self.require_auth()
        if not user:
            return

        prefs = {}
        try:
            if user["notification_prefs_json"]:
                prefs = json.loads(user["notification_prefs_json"])
        except Exception:
            pass

        return self.send_json({
            "profile": {
                "id": user["id"],
                "username": user["username"],
                "email": user["email"],
                "full_name": user["full_name"] or user["username"],
                "phone": user["phone"] or "",
                "role": user["role"],
                "created_at": user["created_at"],
                "notification_prefs": prefs
            }
        })

    def api_customer_update_profile(self):
        user = self.require_auth()
        if not user:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        full_name = str(body.get("full_name", user["full_name"] or "")).strip()
        phone = str(body.get("phone", user["phone"] or "")).strip()
        notification_prefs = body.get("notification_prefs")

        conn = db.get_db()
        with conn:
            if notification_prefs is not None:
                prefs_json = json.dumps(notification_prefs)
                conn.execute("""
                    UPDATE users SET full_name = ?, phone = ?, notification_prefs_json = ?
                    WHERE id = ?
                """, (full_name, phone, prefs_json, user["id"]))
            else:
                conn.execute("""
                    UPDATE users SET full_name = ?, phone = ?
                    WHERE id = ?
                """, (full_name, phone, user["id"]))
        conn.close()

        return self.send_json({"success": True, "message": "Perfil actualizado correctamente"})

    def api_customer_change_password(self):
        user = self.require_auth()
        if not user:
            return

        body = self.read_json_body()
        current_password = str(body.get("current_password", ""))
        new_password = str(body.get("new_password", ""))

        if not current_password or len(new_password) < 8:
            return self.send_error_json("La nueva contraseña debe tener al menos 8 caracteres", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT password_hash, salt FROM users WHERE id = ?", (user["id"],))
        u = cur.fetchone()

        if not db.verify_password(current_password, u["salt"], u["password_hash"]):
            conn.close()
            return self.send_error_json("La contraseña actual no es correcta", 400)

        salt_hex, key_hex = db.hash_password(new_password)
        with conn:
            conn.execute("""
                UPDATE users SET password_hash = ?, salt = ? WHERE id = ?
            """, (key_hex, salt_hex, user["id"]))
        conn.close()

        return self.send_json({"success": True, "message": "Contraseña cambiada exitosamente"})

    def api_customer_delete_account(self):
        """GDPR/Privacy: Allows customer to permanently delete their account and personal data."""
        user = self.require_auth()
        if not user:
            return

        if user["role"] == "admin":
            return self.send_error_json("No se puede eliminar la cuenta principal de administrador", 403)

        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM users WHERE id = ?", (user["id"],))
        conn.close()

        cookie_clear = "innova_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"
        return self.send_json({"success": True, "message": "Cuenta eliminada conforme a tu solicitud"}, headers={"Set-Cookie": cookie_clear})

    # --- Customer Activity History ---
    def api_customer_get_activity(self, query):
        user = self.require_auth()
        if not user:
            return

        limit = min(int(query.get("limit", [50])[0]), 100)
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, event_type, target_id, metadata_json, created_at
            FROM customer_activity
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
        """, (user["id"], limit))
        rows = [dict(r) for r in cur.fetchall()]
        for r in rows:
            try:
                r["metadata"] = json.loads(r["metadata_json"] or "{}")
            except Exception:
                r["metadata"] = {}

        conn.close()
        return self.send_json({"activity": rows, "count": len(rows)})

    def api_customer_record_activity(self):
        user = self.get_authenticated_user()
        body = self.read_json_body()
        if not body:
            return self.send_json({"success": True, "recorded": False})

        event_type = str(body.get("event_type", "")).strip()
        target_id = str(body.get("target_id", "")).strip()
        metadata = body.get("metadata", {})

        # If user is logged in, persist to customer_activity
        if user and event_type:
            conn = db.get_db()
            with conn:
                conn.execute("""
                    INSERT INTO customer_activity (user_id, event_type, target_id, metadata_json)
                    VALUES (?, ?, ?, ?)
                """, (user["id"], event_type, target_id, json.dumps(metadata, ensure_ascii=False)))
            conn.close()
            return self.send_json({"success": True, "recorded": True})

        return self.send_json({"success": True, "recorded": False})

    def api_customer_clear_activity(self):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM customer_activity WHERE user_id = ?", (user["id"],))
        conn.close()
        return self.send_json({"success": True, "message": "Historial de actividad eliminado"})

    # --- Customer Favorites ---
    def api_customer_get_favorites(self):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        cur = conn.cursor()

        # Active promotions
        cur.execute("""
            SELECT id, name, discount_type, discount_value, target_type, target_id
            FROM promotions
            WHERE is_active = 1
              AND datetime(starts_at) <= datetime('now')
              AND datetime(ends_at) >= datetime('now')
        """)
        active_promos = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT p.id, p.name, p.slug, p.category_id, p.price, p.promo_price,
                   p.stock, p.sku, p.short_description, p.featured,
                   c.name as category_name,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image,
                   cf.created_at as favorited_at
            FROM customer_favorites cf
            JOIN products p ON cf.product_id = p.id
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE cf.user_id = ?
            ORDER BY cf.created_at DESC
        """, (user["id"],))
        rows = [dict(r) for r in cur.fetchall()]

        for r in rows:
            price_info = self._calculate_effective_price(r["price"], r["promo_price"], r["category_id"], r["id"], active_promos)
            r.update(price_info)
            r["stock_status"] = "out_of_stock" if r["stock"] <= 0 else "in_stock"
            r["is_available"] = (r["stock"] > 0)

        conn.close()
        return self.send_json({"favorites": rows, "count": len(rows)})

    def api_customer_toggle_favorite(self):
        user = self.require_auth()
        if not user:
            return

        body = self.read_json_body()
        prod_id = str(body.get("product_id", "")).strip() if body else ""
        if not prod_id:
            return self.send_error_json("Identificador de producto requerido", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM customer_favorites WHERE user_id = ? AND product_id = ?", (user["id"], prod_id))
        existing = cur.fetchone()

        with conn:
            if existing:
                conn.execute("DELETE FROM customer_favorites WHERE id = ?", (existing["id"],))
                is_fav = False
                conn.execute("""
                    INSERT INTO customer_activity (user_id, event_type, target_id)
                    VALUES (?, 'remove_favorite', ?)
                """, (user["id"], prod_id))
            else:
                conn.execute("""
                    INSERT INTO customer_favorites (user_id, product_id)
                    VALUES (?, ?)
                """, (user["id"], prod_id))
                is_fav = True
                conn.execute("""
                    INSERT INTO customer_activity (user_id, event_type, target_id)
                    VALUES (?, 'add_favorite', ?)
                """, (user["id"], prod_id))

        conn.close()
        return self.send_json({"success": True, "is_favorite": is_fav})

    def api_customer_remove_favorite(self, prod_id):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM customer_favorites WHERE user_id = ? AND product_id = ?", (user["id"], prod_id))
        conn.close()
        return self.send_json({"success": True, "removed": prod_id})

    # --- Recommendations Engine ---
    def api_customer_get_recommendations(self):
        user = self.get_authenticated_user()
        conn = db.get_db()
        cur = conn.cursor()

        # Active promotions
        cur.execute("""
            SELECT id, name, discount_type, discount_value, target_type, target_id
            FROM promotions
            WHERE is_active = 1
              AND datetime(starts_at) <= datetime('now')
              AND datetime(ends_at) >= datetime('now')
        """)
        active_promos = [dict(r) for r in cur.fetchall()]

        # Active and in-stock products only
        cur.execute("""
            SELECT p.id, p.name, p.slug, p.category_id, p.price, p.promo_price,
                   p.stock, p.sku, p.short_description, p.featured,
                   c.name as category_name,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.status = 'active' AND p.stock > 0
        """)
        active_in_stock = [dict(r) for r in cur.fetchall()]

        if not active_in_stock:
            conn.close()
            return self.send_json({"recommendations": [], "is_personalized": False})

        # Cold start (unauthenticated or no user)
        if not user:
            recs = sorted(active_in_stock, key=lambda x: -x["featured"])[:6]
            for r in recs:
                price_info = self._calculate_effective_price(r["price"], r["promo_price"], r["category_id"], r["id"], active_promos)
                r.update(price_info)
                r["reason"] = "Destacado en INNOVA"
            conn.close()
            return self.send_json({"recommendations": recs, "is_personalized": False})

        user_id = user["id"]

        # Fetch favorites
        cur.execute("SELECT product_id FROM customer_favorites WHERE user_id = ?", (user_id,))
        favorited_ids = {r["product_id"] for r in cur.fetchall()}

        # Fetch recent activity
        cur.execute("""
            SELECT event_type, target_id, metadata_json, created_at
            FROM customer_activity
            WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 100
        """, (user_id,))
        events = [dict(r) for r in cur.fetchall()]

        category_affinity = {}
        viewed_product_ids = set()

        for ev in events:
            etype = ev["event_type"]
            tid = ev["target_id"]
            meta = {}
            try:
                if ev.get("metadata_json"):
                    meta = json.loads(ev["metadata_json"])
            except Exception:
                pass

            cat = meta.get("category_name")
            if etype == "view_product":
                viewed_product_ids.add(tid)
                if cat:
                    category_affinity[cat] = category_affinity.get(cat, 0) + 2
            elif etype == "view_category":
                category_affinity[tid] = category_affinity.get(tid, 0) + 3
            elif etype == "add_favorite":
                if cat:
                    category_affinity[cat] = category_affinity.get(cat, 0) + 4

        has_history = (len(events) >= 2 or len(favorited_ids) >= 1)
        top_categories = sorted(category_affinity.items(), key=lambda x: -x[1])
        top_cat_names = [c[0] for c in top_categories[:2]]

        scored_products = []
        for p in active_in_stock:
            score = 0.0
            reason = "Recomendado para ti"
            cat_name = p.get("category_name")

            price_info = self._calculate_effective_price(p["price"], p["promo_price"], p["category_id"], p["id"], active_promos)
            p.update(price_info)

            if has_history:
                if cat_name in category_affinity:
                    score += min(category_affinity[cat_name] * 3, 20)
                    if cat_name in top_cat_names:
                        reason = f"Porque te interesa {cat_name}"

                if p["id"] in favorited_ids:
                    score += 5
                    reason = "De tus productos favoritos"
                elif p["id"] in viewed_product_ids:
                    score += 4
                    reason = "Visto recientemente"

                if p["has_discount"]:
                    score += 6
                    if score < 12:
                        reason = f"En oferta: -{p['discount_percent']}%"

                if p["featured"]:
                    score += 3
            else:
                if p["featured"]:
                    score += 10
                    reason = "Selección destacada para nuevos clientes"
                elif p["has_discount"]:
                    score += 8
                    reason = f"En oferta especial: -{p['discount_percent']}%"
                else:
                    score += 2
                    reason = "Popular en la tienda"

            p["score"] = score
            p["reason"] = reason
            scored_products.append(p)

        scored_products.sort(key=lambda x: -x["score"])
        recommendations = scored_products[:6]

        conn.close()
        return self.send_json({
            "recommendations": recommendations,
            "is_personalized": has_history,
            "top_categories": top_cat_names
        })

    # --- Customer Notifications Center ---
    def api_customer_get_notifications(self):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT un.id, un.notification_id, un.is_read, un.read_at, un.created_at,
                   n.title, n.message, n.type, n.link_url
            FROM user_notifications un
            JOIN notifications n ON un.notification_id = n.id
            WHERE un.user_id = ? AND un.is_deleted = 0
            ORDER BY un.created_at DESC LIMIT 50
        """, (user["id"],))
        rows = [dict(r) for r in cur.fetchall()]

        unread_count = sum(1 for r in rows if not r["is_read"])
        conn.close()
        return self.send_json({"notifications": rows, "unread_count": unread_count})

    def api_customer_read_notification(self, notif_user_id):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        with conn:
            conn.execute("""
                UPDATE user_notifications
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE id = ? AND user_id = ?
            """, (notif_user_id, user["id"]))
        conn.close()
        return self.send_json({"success": True})

    def api_customer_mark_all_notifications_read(self):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        with conn:
            conn.execute("""
                UPDATE user_notifications
                SET is_read = 1, read_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND is_read = 0 AND is_deleted = 0
            """, (user["id"],))
        conn.close()
        return self.send_json({"success": True})

    def api_customer_delete_notification(self, notif_user_id):
        user = self.require_auth()
        if not user:
            return

        conn = db.get_db()
        with conn:
            conn.execute("""
                UPDATE user_notifications SET is_deleted = 1
                WHERE id = ? AND user_id = ?
            """, (notif_user_id, user["id"]))
        conn.close()
        return self.send_json({"success": True})

    # =========================================================
    # ADMIN NOTIFICATIONS MANAGEMENT
    # =========================================================
    def api_admin_get_notifications(self, query):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT n.*,
                   (SELECT COUNT(*) FROM user_notifications WHERE notification_id = n.id) as total_sent,
                   (SELECT COUNT(*) FROM user_notifications WHERE notification_id = n.id AND is_read = 1) as total_read
            FROM notifications n
            ORDER BY n.created_at DESC LIMIT 50
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return self.send_json({"campaigns": rows, "count": len(rows)})

    def api_admin_send_notification(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        title = str(body.get("title", "")).strip()
        message = str(body.get("message", "")).strip()
        notif_type = str(body.get("type", "promotion")).strip()
        target_type = str(body.get("target_type", "all")).strip()
        target_id = body.get("target_id")
        link_url = str(body.get("link_url", "")).strip() or "#catalogo"

        if not title or not message:
            return self.send_error_json("El título y el mensaje son obligatorios", 400)

        conn = db.get_db()
        cur = conn.cursor()

        # Fetch eligible customers
        cur.execute("SELECT id, notification_prefs_json FROM users WHERE role = 'cliente'")
        customers = cur.fetchall()

        recipients = []
        for c in customers:
            prefs = {}
            try:
                if c["notification_prefs_json"]:
                    prefs = json.loads(c["notification_prefs_json"])
            except Exception:
                prefs = {}

            # Respect customer preferences
            if notif_type == "promotion" and prefs.get("promotions") is False:
                continue
            if notif_type == "new_product" and prefs.get("new_products") is False:
                continue
            if notif_type in ("price_drop", "restock") and prefs.get("stock_alerts") is False:
                continue

            recipients.append(c["id"])

        with conn:
            cur.execute("""
                INSERT INTO notifications (title, message, type, target_type, target_id, link_url, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (title, message, notif_type, target_type, str(target_id) if target_id else None, link_url, admin["id"]))
            notif_id = cur.lastrowid

            for uid in recipients:
                conn.execute("""
                    INSERT INTO user_notifications (notification_id, user_id)
                    VALUES (?, ?)
                """, (notif_id, uid))

        conn.close()
        return self.send_json({
            "success": True,
            "notification_id": notif_id,
            "recipients_count": len(recipients)
        }, status=201)

    def api_admin_delete_notification(self, notif_id):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM notifications WHERE id = ?", (notif_id,))
        conn.close()
        return self.send_json({"success": True, "deleted_id": notif_id})

    # =========================================================
    # DASHBOARD ENDPOINT
    # =========================================================
    def api_dashboard(self):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()

        cur.execute("SELECT value FROM settings WHERE key = 'low_stock_threshold'")
        setting_row = cur.fetchone()
        threshold = int(setting_row["value"]) if setting_row else 5

        cur.execute("SELECT COUNT(*) as c FROM products")
        total_products = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) as c FROM products WHERE status = 'active'")
        active_products = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) as c FROM products WHERE stock = 0")
        out_of_stock = cur.fetchone()["c"]

        cur.execute("SELECT COUNT(*) as c FROM products WHERE stock > 0 AND stock <= ?", (threshold,))
        low_stock = cur.fetchone()["c"]

        cur.execute("""
            SELECT COUNT(*) as c FROM promotions
            WHERE is_active = 1
              AND datetime(starts_at) <= datetime('now')
              AND datetime(ends_at) >= datetime('now')
        """)
        active_promotions = cur.fetchone()["c"]

        # Total registered customers count
        cur.execute("SELECT COUNT(*) as c FROM users WHERE role = 'cliente'")
        total_customers = cur.fetchone()["c"]

        cur.execute("""
            SELECT p.id, p.name, p.price, p.stock, p.status, p.created_at, c.name as category_name
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            ORDER BY p.created_at DESC LIMIT 5
        """)
        latest_products = [dict(r) for r in cur.fetchall()]

        cur.execute("""
            SELECT sm.id, sm.product_id, p.name as product_name, sm.previous_stock,
                   sm.new_stock, sm.delta, sm.reason, sm.created_at, u.username as user_name
            FROM stock_movements sm
            LEFT JOIN products p ON sm.product_id = p.id
            LEFT JOIN users u ON sm.user_id = u.id
            ORDER BY sm.created_at DESC LIMIT 6
        """)
        recent_movements = [dict(r) for r in cur.fetchall()]

        conn.close()

        return self.send_json({
            "metrics": {
                "total_products": total_products,
                "active_products": active_products,
                "out_of_stock": out_of_stock,
                "low_stock": low_stock,
                "low_stock_threshold": threshold,
                "active_promotions": active_promotions,
                "total_customers": total_customers
            },
            "latest_products": latest_products,
            "recent_movements": recent_movements
        })

    # =========================================================
    # PRODUCTS ENDPOINTS
    # =========================================================
    def _calculate_effective_price(self, price, promo_price, category_id, product_id, active_promos):
        best_discount = 0.0
        promo_name = None

        if promo_price is not None and 0 <= promo_price < price:
            best_discount = price - promo_price
            promo_name = "Precio especial"

        for p in active_promos:
            matches = False
            if p["target_type"] == "all":
                matches = True
            elif p["target_type"] == "category" and str(p["target_id"]) == str(category_id):
                matches = True
            elif p["target_type"] == "product" and str(p["target_id"]) == str(product_id):
                matches = True

            if matches:
                discount = 0.0
                if p["discount_type"] == "percent":
                    discount = price * (float(p["discount_value"]) / 100.0)
                elif p["discount_type"] == "fixed":
                    discount = min(price, float(p["discount_value"]))

                if discount > best_discount:
                    best_discount = discount
                    promo_name = p["name"]

        effective_price = max(0.0, round(price - best_discount, 2))
        has_discount = best_discount > 0 and effective_price < price
        discount_percent = round((best_discount / price) * 100) if (has_discount and price > 0) else 0

        return {
            "effective_price": effective_price,
            "has_discount": has_discount,
            "discount_percent": discount_percent,
            "discount_amount": round(best_discount, 2),
            "promo_name": promo_name
        }

    def api_get_products(self, query):
        user = self.get_authenticated_user()
        is_admin_request = bool(user and user["role"] == "admin" and query.get("all", ["0"])[0] in ("1", "true"))

        conn = db.get_db()
        cur = conn.cursor()

        cur.execute("SELECT value FROM settings WHERE key = 'low_stock_threshold'")
        s_row = cur.fetchone()
        threshold = int(s_row["value"]) if s_row else 5

        cur.execute("""
            SELECT id, name, discount_type, discount_value, target_type, target_id
            FROM promotions
            WHERE is_active = 1
              AND datetime(starts_at) <= datetime('now')
              AND datetime(ends_at) >= datetime('now')
        """)
        active_promos = [dict(r) for r in cur.fetchall()]

        conditions = []
        params = []

        if not is_admin_request:
            conditions.append("p.status = 'active'")

        category_filter = query.get("category", [None])[0]
        if category_filter and category_filter != "Todos":
            conditions.append("(c.name = ? OR c.slug = ?)")
            params.extend([category_filter, category_filter])

        search = query.get("search", [""])[0].strip()
        if search:
            conditions.append("(p.name LIKE ? OR p.short_description LIKE ? OR p.sku LIKE ?)")
            term = f"%{search}%"
            params.extend([term, term, term])

        status_filter = query.get("status", [None])[0]
        if status_filter and is_admin_request:
            conditions.append("p.status = ?")
            params.append(status_filter)

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT p.id, p.name, p.slug, p.category_id, p.price, p.promo_price,
                   p.stock, p.sku, p.short_description, p.full_description,
                   p.status, p.featured, p.specs_json, p.created_at, p.updated_at,
                   c.name as category_name, c.slug as category_slug,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC, sort_order ASC LIMIT 1) as primary_image
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            {where_clause}
            ORDER BY p.featured DESC, p.created_at DESC
        """
        cur.execute(sql, params)
        rows = cur.fetchall()

        products = []
        for r in rows:
            p_dict = dict(r)
            try:
                p_dict["specs"] = json.loads(p_dict.get("specs_json") or "[]")
            except Exception:
                p_dict["specs"] = []

            price_info = self._calculate_effective_price(
                p_dict["price"], p_dict["promo_price"], p_dict["category_id"], p_dict["id"], active_promos
            )
            p_dict.update(price_info)

            if p_dict["stock"] <= 0:
                p_dict["stock_status"] = "out_of_stock"
                p_dict["is_available"] = False
            elif p_dict["stock"] <= threshold:
                p_dict["stock_status"] = "low_stock"
                p_dict["is_available"] = True
            else:
                p_dict["stock_status"] = "in_stock"
                p_dict["is_available"] = True

            products.append(p_dict)

        conn.close()
        return self.send_json({"products": products, "count": len(products)})

    def api_get_product_detail(self, prod_id):
        conn = db.get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT p.*, c.name as category_name, c.slug as category_slug
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE p.id = ?
        """, (prod_id,))
        row = cur.fetchone()

        if not row:
            conn.close()
            return self.send_error_json("Producto no encontrado", 404)

        product = dict(row)
        try:
            product["specs"] = json.loads(product.get("specs_json") or "[]")
        except Exception:
            product["specs"] = []

        cur.execute("""
            SELECT id, image_url, is_primary, sort_order
            FROM product_images
            WHERE product_id = ?
            ORDER BY is_primary DESC, sort_order ASC
        """, (prod_id,))
        images = [dict(img) for img in cur.fetchall()]
        product["images"] = images
        product["primary_image"] = images[0]["image_url"] if images else None

        cur.execute("""
            SELECT id, name, discount_type, discount_value, target_type, target_id
            FROM promotions
            WHERE is_active = 1
              AND datetime(starts_at) <= datetime('now')
              AND datetime(ends_at) >= datetime('now')
        """)
        active_promos = [dict(r) for r in cur.fetchall()]

        price_info = self._calculate_effective_price(
            product["price"], product["promo_price"], product["category_id"], product["id"], active_promos
        )
        product.update(price_info)

        cur.execute("SELECT value FROM settings WHERE key = 'low_stock_threshold'")
        s_row = cur.fetchone()
        threshold = int(s_row["value"]) if s_row else 5

        if product["stock"] <= 0:
            product["stock_status"] = "out_of_stock"
            product["is_available"] = False
        elif product["stock"] <= threshold:
            product["stock_status"] = "low_stock"
            product["is_available"] = True
        else:
            product["stock_status"] = "in_stock"
            product["is_available"] = True

        conn.close()
        return self.send_json({"product": product})

    def api_create_product(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        name = str(body.get("name", "")).strip()
        if not name:
            return self.send_error_json("El nombre del producto es obligatorio", 400)

        price = body.get("price")
        try:
            price = float(price)
            if price < 0:
                raise ValueError()
        except (TypeError, ValueError):
            return self.send_error_json("El precio debe ser un número mayor o igual a 0", 400)

        promo_price = body.get("promo_price")
        if promo_price not in (None, ""):
            try:
                promo_price = float(promo_price)
                if promo_price < 0 or promo_price >= price:
                    return self.send_error_json("El precio promocional debe ser menor al precio normal", 400)
            except (TypeError, ValueError):
                return self.send_error_json("Precio promocional inválido", 400)
        else:
            promo_price = None

        stock = body.get("stock", 0)
        try:
            stock = int(stock)
            if stock < 0:
                raise ValueError()
        except (TypeError, ValueError):
            return self.send_error_json("El inventario debe ser un número entero mayor o igual a 0", 400)

        raw_slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        prod_id = body.get("id") or f"{raw_slug}-{secrets.token_hex(3)}"
        slug = raw_slug

        category_id = body.get("category_id")
        sku = str(body.get("sku", "")).strip() or f"SKU-{prod_id[:8].upper()}"
        short_desc = str(body.get("short_description", "")).strip()
        full_desc = str(body.get("full_description", "")).strip()
        status = body.get("status", "active")
        if status not in ("active", "inactive", "draft"):
            status = "active"

        featured = 1 if body.get("featured") else 0
        specs = body.get("specs", [])
        if not isinstance(specs, list):
            specs = []
        specs_json = json.dumps(specs, ensure_ascii=False)

        images = body.get("images", [])

        conn = db.get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM products WHERE id = ?", (prod_id,))
        if cur.fetchone():
            conn.close()
            return self.send_error_json(f"Ya existe un producto con el identificador '{prod_id}'", 409)

        with conn:
            conn.execute("""
                INSERT INTO products (
                    id, name, slug, category_id, price, promo_price, stock, sku,
                    short_description, full_description, status, featured, specs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prod_id, name, slug, category_id, price, promo_price, stock, sku,
                short_desc, full_desc, status, featured, specs_json
            ))

            if images:
                for idx, img in enumerate(images):
                    img_url = img if isinstance(img, str) else img.get("image_url", "")
                    if img_url:
                        is_primary = 1 if idx == 0 else 0
                        conn.execute("""
                            INSERT INTO product_images (product_id, image_url, is_primary, sort_order)
                            VALUES (?, ?, ?, ?)
                        """, (prod_id, img_url, is_primary, idx))

            conn.execute("""
                INSERT INTO stock_movements (product_id, user_id, previous_stock, new_stock, delta, reason)
                VALUES (?, ?, 0, ?, ?, 'Creación de producto con inventario inicial')
            """, (prod_id, admin["id"], stock, stock))

        conn.close()
        return self.send_json({"success": True, "product_id": prod_id}, status=201)

    def api_admin_duplicate_product(self, source_id):
        """Duplicates a product creating an editable copy in draft status."""
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (source_id,))
        source = cur.fetchone()
        if not source:
            conn.close()
            return self.send_error_json("Producto de origen no encontrado", 404)

        base_id = f"{source['id']}-copia"
        new_id = base_id
        idx = 1
        while True:
            cur.execute("SELECT id FROM products WHERE id = ?", (new_id,))
            if not cur.fetchone():
                break
            new_id = f"{base_id}-{idx}"
            idx += 1

        new_name = f"{source['name']} (Copia)"
        new_sku = f"{source['sku'] or source['id']}-COP"[:30]

        with conn:
            conn.execute("""
                INSERT INTO products (
                    id, name, slug, category_id, price, promo_price, stock, sku,
                    short_description, full_description, status, featured, specs_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'draft', 0, ?)
            """, (
                new_id, new_name, new_id, source["category_id"], source["price"],
                source["promo_price"], source["stock"], new_sku,
                source["short_description"], source["full_description"],
                source["specs_json"]
            ))

            # Duplicate images
            cur.execute("SELECT image_url, is_primary, sort_order FROM product_images WHERE product_id = ?", (source_id,))
            for img in cur.fetchall():
                conn.execute("""
                    INSERT INTO product_images (product_id, image_url, is_primary, sort_order)
                    VALUES (?, ?, ?, ?)
                """, (new_id, img["image_url"], img["is_primary"], img["sort_order"]))

            if source["stock"] > 0:
                conn.execute("""
                    INSERT INTO stock_movements (product_id, user_id, previous_stock, new_stock, delta, reason)
                    VALUES (?, ?, 0, ?, ?, 'Duplicación de producto')
                """, (new_id, admin["id"], source["stock"], source["stock"]))

        conn.close()
        return self.send_json({"success": True, "product_id": new_id, "message": "Producto duplicado exitosamente en estado borrador"})

    def api_update_product(self, prod_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM products WHERE id = ?", (prod_id,))
        existing = cur.fetchone()
        if not existing:
            conn.close()
            return self.send_error_json("Producto no encontrado", 404)

        name = str(body.get("name", existing["name"])).strip()
        if not name:
            conn.close()
            return self.send_error_json("El nombre del producto no puede estar vacío", 400)

        price = body.get("price", existing["price"])
        try:
            price = float(price)
            if price < 0:
                raise ValueError()
        except (TypeError, ValueError):
            conn.close()
            return self.send_error_json("El precio debe ser un número mayor o igual a 0", 400)

        promo_price = body.get("promo_price")
        if promo_price not in (None, "", "null"):
            try:
                promo_price = float(promo_price)
                if promo_price < 0 or promo_price >= price:
                    conn.close()
                    return self.send_error_json("El precio promocional debe ser menor al precio normal", 400)
            except (TypeError, ValueError):
                conn.close()
                return self.send_error_json("Precio promocional inválido", 400)
        else:
            promo_price = None

        new_stock = body.get("stock", existing["stock"])
        try:
            new_stock = int(new_stock)
            if new_stock < 0:
                raise ValueError()
        except (TypeError, ValueError):
            conn.close()
            return self.send_error_json("El inventario debe ser un entero mayor o igual a 0", 400)

        category_id = body.get("category_id", existing["category_id"])
        sku = str(body.get("sku", existing["sku"] or "")).strip()
        short_desc = str(body.get("short_description", existing["short_description"] or "")).strip()
        full_desc = str(body.get("full_description", existing["full_description"] or "")).strip()

        status = body.get("status", existing["status"])
        if status not in ("active", "inactive", "draft"):
            status = existing["status"]

        featured = 1 if body.get("featured", existing["featured"]) else 0

        specs = body.get("specs")
        if specs is not None:
            if not isinstance(specs, list):
                specs = []
            specs_json = json.dumps(specs, ensure_ascii=False)
        else:
            specs_json = existing["specs_json"]

        previous_stock = existing["stock"]
        stock_changed = (new_stock != previous_stock)

        with conn:
            conn.execute("""
                UPDATE products
                SET name = ?, category_id = ?, price = ?, promo_price = ?, stock = ?,
                    sku = ?, short_description = ?, full_description = ?, status = ?,
                    featured = ?, specs_json = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (
                name, category_id, price, promo_price, new_stock, sku,
                short_desc, full_desc, status, featured, specs_json, prod_id
            ))

            if stock_changed:
                delta = new_stock - previous_stock
                conn.execute("""
                    INSERT INTO stock_movements (product_id, user_id, previous_stock, new_stock, delta, reason)
                    VALUES (?, ?, ?, ?, ?, 'Ajuste desde edición de producto')
                """, (prod_id, admin["id"], previous_stock, new_stock, delta))

            images = body.get("images")
            if images is not None:
                conn.execute("DELETE FROM product_images WHERE product_id = ?", (prod_id,))
                for idx, img in enumerate(images):
                    img_url = img if isinstance(img, str) else img.get("image_url", "")
                    if img_url:
                        is_primary = 1 if idx == 0 else 0
                        conn.execute("""
                            INSERT INTO product_images (product_id, image_url, is_primary, sort_order)
                            VALUES (?, ?, ?, ?)
                        """, (prod_id, img_url, is_primary, idx))

        conn.close()
        return self.send_json({"success": True, "product_id": prod_id})

    def api_patch_product_status(self, prod_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        status = body.get("status") if body else None
        if status not in ("active", "inactive", "draft"):
            return self.send_error_json("Estado inválido. Opciones: active, inactive, draft", 400)

        conn = db.get_db()
        with conn:
            conn.execute("UPDATE products SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, prod_id))
        conn.close()
        return self.send_json({"success": True, "product_id": prod_id, "status": status})

    def api_patch_product_featured(self, prod_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        featured = 1 if (body and body.get("featured")) else 0

        conn = db.get_db()
        with conn:
            conn.execute("UPDATE products SET featured = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (featured, prod_id))
        conn.close()
        return self.send_json({"success": True, "product_id": prod_id, "featured": bool(featured)})

    def api_delete_product(self, prod_id):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM products WHERE id = ?", (prod_id,))
        if not cur.fetchone():
            conn.close()
            return self.send_error_json("Producto no encontrado", 404)

        with conn:
            conn.execute("DELETE FROM products WHERE id = ?", (prod_id,))

        conn.close()
        return self.send_json({"success": True, "deleted_id": prod_id})

    # =========================================================
    # INVENTORY ENDPOINTS
    # =========================================================
    def api_get_inventory(self, query):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()

        cur.execute("SELECT value FROM settings WHERE key = 'low_stock_threshold'")
        s_row = cur.fetchone()
        threshold = int(s_row["value"]) if s_row else 5

        filter_type = query.get("filter", ["all"])[0]
        conditions = []
        params = []

        if filter_type == "low":
            conditions.append("p.stock > 0 AND p.stock <= ?")
            params.append(threshold)
        elif filter_type == "out":
            conditions.append("p.stock = 0")
        elif filter_type == "in":
            conditions.append("p.stock > ?")
            params.append(threshold)

        search = query.get("search", [""])[0].strip()
        if search:
            conditions.append("(p.name LIKE ? OR p.sku LIKE ?)")
            term = f"%{search}%"
            params.extend([term, term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        sql = f"""
            SELECT p.id, p.name, p.sku, p.stock, p.price, p.status, c.name as category_name,
                   (SELECT image_url FROM product_images WHERE product_id = p.id ORDER BY is_primary DESC LIMIT 1) as image_url,
                   (SELECT created_at FROM stock_movements WHERE product_id = p.id ORDER BY created_at DESC LIMIT 1) as last_movement
            FROM products p
            LEFT JOIN categories c ON p.category_id = c.id
            {where_clause}
            ORDER BY p.stock ASC, p.name ASC
        """
        cur.execute(sql, params)
        rows = [dict(r) for r in cur.fetchall()]

        for item in rows:
            if item["stock"] <= 0:
                item["stock_status"] = "out_of_stock"
            elif item["stock"] <= threshold:
                item["stock_status"] = "low_stock"
            else:
                item["stock_status"] = "in_stock"

        conn.close()
        return self.send_json({"inventory": rows, "threshold": threshold, "count": len(rows)})

    def api_adjust_inventory(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        prod_id = body.get("product_id")
        action = body.get("action")
        quantity = body.get("quantity")
        reason = str(body.get("reason", "")).strip() or "Ajuste manual de inventario"

        if not prod_id or action not in ("add", "subtract", "set") or quantity is None:
            return self.send_error_json("Parámetros de ajuste incompletos", 400)

        try:
            quantity = int(quantity)
            if quantity < 0:
                raise ValueError()
        except (TypeError, ValueError):
            return self.send_error_json("La cantidad debe ser un entero positivo", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id, name, stock FROM products WHERE id = ?", (prod_id,))
        prod = cur.fetchone()
        if not prod:
            conn.close()
            return self.send_error_json("Producto no encontrado", 404)

        prev_stock = prod["stock"]

        if action == "add":
            new_stock = prev_stock + quantity
            delta = quantity
        elif action == "subtract":
            if quantity > prev_stock:
                conn.close()
                return self.send_error_json(
                    f"No se puede restar {quantity} unidades. El stock actual es de {prev_stock} unidades.", 400
                )
            new_stock = prev_stock - quantity
            delta = -quantity
        elif action == "set":
            new_stock = quantity
            delta = new_stock - prev_stock

        with conn:
            conn.execute("UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (new_stock, prod_id))
            conn.execute("""
                INSERT INTO stock_movements (product_id, user_id, previous_stock, new_stock, delta, reason)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (prod_id, admin["id"], prev_stock, new_stock, delta, reason))

        conn.close()
        return self.send_json({
            "success": True,
            "product_id": prod_id,
            "previous_stock": prev_stock,
            "new_stock": new_stock,
            "delta": delta
        })

    def api_get_stock_movements(self, query):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()

        prod_id = query.get("product_id", [None])[0]
        limit = min(int(query.get("limit", [50])[0]), 100)

        if prod_id:
            cur.execute("""
                SELECT sm.*, p.name as product_name, p.sku as product_sku, u.username as user_name
                FROM stock_movements sm
                LEFT JOIN products p ON sm.product_id = p.id
                LEFT JOIN users u ON sm.user_id = u.id
                WHERE sm.product_id = ?
                ORDER BY sm.created_at DESC LIMIT ?
            """, (prod_id, limit))
        else:
            cur.execute("""
                SELECT sm.*, p.name as product_name, p.sku as product_sku, u.username as user_name
                FROM stock_movements sm
                LEFT JOIN products p ON sm.product_id = p.id
                LEFT JOIN users u ON sm.user_id = u.id
                ORDER BY sm.created_at DESC LIMIT ?
            """, (limit,))

        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return self.send_json({"movements": rows, "count": len(rows)})

    # =========================================================
    # PROMOTIONS ENDPOINTS
    # =========================================================
    def api_get_promotions(self, query):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT prom.*,
                   CASE
                       WHEN prom.target_type = 'category' THEN (SELECT name FROM categories WHERE id = prom.target_id)
                       WHEN prom.target_type = 'product' THEN (SELECT name FROM products WHERE id = prom.target_id)
                       ELSE 'Todos los productos'
                   END as target_name
            FROM promotions prom
            ORDER BY prom.created_at DESC
        """)
        rows = cur.fetchall()

        promotions = []
        now = datetime.utcnow()

        for r in rows:
            p_dict = dict(r)
            try:
                starts = datetime.strptime(p_dict["starts_at"], "%Y-%m-%d %H:%M:%S")
                ends = datetime.strptime(p_dict["ends_at"], "%Y-%m-%d %H:%M:%S")
            except Exception:
                try:
                    starts = datetime.strptime(p_dict["starts_at"][:19], "%Y-%m-%d %H:%M:%S")
                    ends = datetime.strptime(p_dict["ends_at"][:19], "%Y-%m-%d %H:%M:%S")
                except Exception:
                    starts = now
                    ends = now

            if not p_dict["is_active"]:
                p_dict["status"] = "inactive"
            elif now < starts:
                p_dict["status"] = "scheduled"
            elif now > ends:
                p_dict["status"] = "expired"
            else:
                p_dict["status"] = "active"

            promotions.append(p_dict)

        conn.close()
        return self.send_json({"promotions": promotions, "count": len(promotions)})

    def api_create_promotion(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        name = str(body.get("name", "")).strip()
        if not name:
            return self.send_error_json("El nombre de la promoción es obligatorio", 400)

        discount_type = body.get("discount_type")
        if discount_type not in ("percent", "fixed"):
            return self.send_error_json("Tipo de descuento inválido ('percent' o 'fixed')", 400)

        discount_value = body.get("discount_value")
        try:
            discount_value = float(discount_value)
            if discount_value <= 0:
                raise ValueError()
            if discount_type == "percent" and discount_value > 100:
                return self.send_error_json("El porcentaje de descuento no puede ser superior al 100%", 400)
        except (TypeError, ValueError):
            return self.send_error_json("Valor de descuento inválido", 400)

        target_type = body.get("target_type", "all")
        if target_type not in ("all", "category", "product"):
            target_type = "all"
        target_id = body.get("target_id")
        if target_type in ("category", "product") and not target_id:
            return self.send_error_json(f"Debe especificar el ID de {target_type} seleccionado", 400)

        starts_at = str(body.get("starts_at", "")).strip()
        ends_at = str(body.get("ends_at", "")).strip()

        if len(starts_at) == 16:
            starts_at = starts_at.replace("T", " ") + ":00"
        if len(ends_at) == 16:
            ends_at = ends_at.replace("T", " ") + ":00"

        if not starts_at or not ends_at:
            return self.send_error_json("Las fechas de inicio y fin son obligatorias", 400)

        if ends_at <= starts_at:
            return self.send_error_json("La fecha de finalización debe ser posterior a la de inicio", 400)

        description = str(body.get("description", "")).strip()
        is_active = 1 if body.get("is_active", True) else 0

        conn = db.get_db()
        with conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO promotions (
                    name, description, discount_type, discount_value,
                    target_type, target_id, starts_at, ends_at, is_active
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, description, discount_type, discount_value, target_type, target_id, starts_at, ends_at, is_active))
            promo_id = cur.lastrowid

        conn.close()
        return self.send_json({"success": True, "promotion_id": promo_id}, status=201)

    def api_update_promotion(self, promo_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body:
            return self.send_error_json("Datos de solicitud inválidos", 400)

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT * FROM promotions WHERE id = ?", (promo_id,))
        existing = cur.fetchone()
        if not existing:
            conn.close()
            return self.send_error_json("Promoción no encontrada", 404)

        name = str(body.get("name", existing["name"])).strip()
        discount_type = body.get("discount_type", existing["discount_type"])
        discount_value = body.get("discount_value", existing["discount_value"])
        try:
            discount_value = float(discount_value)
            if discount_value <= 0:
                raise ValueError()
            if discount_type == "percent" and discount_value > 100:
                conn.close()
                return self.send_error_json("El porcentaje de descuento no puede ser superior al 100%", 400)
        except (TypeError, ValueError):
            conn.close()
            return self.send_error_json("Valor de descuento inválido", 400)

        target_type = body.get("target_type", existing["target_type"])
        target_id = body.get("target_id", existing["target_id"])

        starts_at = str(body.get("starts_at", existing["starts_at"])).strip().replace("T", " ")
        ends_at = str(body.get("ends_at", existing["ends_at"])).strip().replace("T", " ")

        if len(starts_at) == 16:
            starts_at += ":00"
        if len(ends_at) == 16:
            ends_at += ":00"

        if ends_at <= starts_at:
            conn.close()
            return self.send_error_json("La fecha de finalización debe ser posterior a la de inicio", 400)

        description = str(body.get("description", existing["description"] or "")).strip()
        is_active = 1 if body.get("is_active", existing["is_active"]) else 0

        with conn:
            conn.execute("""
                UPDATE promotions
                SET name = ?, description = ?, discount_type = ?, discount_value = ?,
                    target_type = ?, target_id = ?, starts_at = ?, ends_at = ?, is_active = ?
                WHERE id = ?
            """, (name, description, discount_type, discount_value, target_type, target_id, starts_at, ends_at, is_active, promo_id))

        conn.close()
        return self.send_json({"success": True, "promotion_id": promo_id})

    def api_patch_promotion_status(self, promo_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        is_active = 1 if (body and body.get("is_active")) else 0

        conn = db.get_db()
        with conn:
            conn.execute("UPDATE promotions SET is_active = ? WHERE id = ?", (is_active, promo_id))
        conn.close()
        return self.send_json({"success": True, "promotion_id": promo_id, "is_active": bool(is_active)})

    def api_delete_promotion(self, promo_id):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM promotions WHERE id = ?", (promo_id,))
        conn.close()
        return self.send_json({"success": True, "deleted_id": promo_id})

    # =========================================================
    # CATEGORIES ENDPOINTS
    # =========================================================
    def api_get_categories(self):
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("""
            SELECT c.*,
                   (SELECT COUNT(*) FROM products WHERE category_id = c.id) as product_count,
                   (SELECT COUNT(*) FROM products WHERE category_id = c.id AND status = 'active') as active_product_count
            FROM categories c
            ORDER BY c.name ASC
        """)
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return self.send_json({"categories": rows, "count": len(rows)})

    def api_create_category(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        name = str(body.get("name", "")).strip() if body else ""
        if not name:
            return self.send_error_json("El nombre de la categoría es obligatorio", 400)

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        description = str(body.get("description", "")).strip()
        image_url = body.get("image_url")

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT id FROM categories WHERE name = ?", (name,))
        if cur.fetchone():
            conn.close()
            return self.send_error_json("Ya existe una categoría con ese nombre", 409)

        with conn:
            cur.execute("""
                INSERT INTO categories (name, slug, description, image_url)
                VALUES (?, ?, ?, ?)
            """, (name, slug, description, image_url))
            cat_id = cur.lastrowid

        conn.close()
        return self.send_json({"success": True, "category_id": cat_id}, status=201)

    def api_update_category(self, cat_id):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        name = str(body.get("name", "")).strip() if body else ""
        if not name:
            return self.send_error_json("El nombre de la categoría es obligatorio", 400)

        slug = re.sub(r"[^a-zA-Z0-9]+", "-", name.lower()).strip("-")
        description = str(body.get("description", "")).strip()
        image_url = body.get("image_url")

        conn = db.get_db()
        with conn:
            conn.execute("""
                UPDATE categories
                SET name = ?, slug = ?, description = ?, image_url = ?
                WHERE id = ?
            """, (name, slug, description, image_url, cat_id))
        conn.close()
        return self.send_json({"success": True, "category_id": cat_id})

    def api_delete_category(self, cat_id):
        admin = self.require_admin()
        if not admin:
            return

        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM products WHERE category_id = ?", (cat_id,))
        count = cur.fetchone()["c"]
        if count > 0:
            conn.close()
            return self.send_error_json(
                f"No se puede eliminar la categoría porque tiene {count} productos asociados. Reasigne o elimine los productos primero.",
                400
            )

        with conn:
            conn.execute("DELETE FROM categories WHERE id = ?", (cat_id,))
        conn.close()
        return self.send_json({"success": True, "deleted_id": cat_id})

    # =========================================================
    # SETTINGS ENDPOINTS
    # =========================================================
    def api_get_settings(self):
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT key, value FROM settings")
        rows = cur.fetchall()
        settings = {r["key"]: r["value"] for r in rows}
        conn.close()
        return self.send_json({"settings": settings})

    def api_update_settings(self):
        admin = self.require_admin()
        if not admin:
            return

        body = self.read_json_body()
        if not body or not isinstance(body, dict):
            return self.send_error_json("Datos de configuración inválidos", 400)

        allowed_keys = {
            "store_name", "store_tagline", "whatsapp_url", "whatsapp_phone",
            "contact_email", "currency_code", "currency_symbol",
            "low_stock_threshold", "announcement"
        }

        conn = db.get_db()
        with conn:
            for k, v in body.items():
                if k in allowed_keys:
                    conn.execute("""
                        INSERT OR REPLACE INTO settings (key, value, updated_at)
                        VALUES (?, ?, CURRENT_TIMESTAMP)
                    """, (k, str(v)))

        conn.close()
        return self.send_json({"success": True})

    # =========================================================
    # FILE UPLOAD ENDPOINT (SECURE)
    # =========================================================
    def api_upload(self):
        admin = self.require_admin()
        if not admin:
            return

        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("multipart/form-data"):
            return self.send_error_json("Se requiere multipart/form-data para subir imágenes", 400)

        match = re.search(r'boundary=([^;]+)', content_type)
        if not match:
            return self.send_error_json("Boundary de multipart no encontrado", 400)

        boundary = match.group(1).strip().strip('"').encode("utf-8")
        content_length = int(self.headers.get("Content-Length", 0))

        if content_length > 5 * 1024 * 1024:
            return self.send_error_json("El archivo supera el tamaño máximo permitido de 5 MB", 400)

        raw_data = self.rfile.read(content_length)
        parts = raw_data.split(b"--" + boundary)
        file_bytes = None
        detected_ext = None

        for part in parts:
            if b'Content-Disposition:' in part and b'filename=' in part:
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    continue
                file_bytes = part[header_end + 4:].rstrip(b"\r\n")
                break

        if not file_bytes:
            return self.send_error_json("No se encontró ningún archivo en la solicitud", 400)

        # Magic Bytes Validation
        if file_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
            detected_ext = ".png"
        elif file_bytes.startswith(b"\xff\xd8\xff"):
            detected_ext = ".jpg"
        elif file_bytes.startswith(b"RIFF") and b"WEBP" in file_bytes[:16]:
            detected_ext = ".webp"
        elif file_bytes.startswith(b"GIF87a") or file_bytes.startswith(b"GIF89a"):
            detected_ext = ".gif"
        else:
            return self.send_error_json(
                "Formato de imagen no permitido. Solo se aceptan PNG, JPG, WebP o GIF legítimos.", 400
            )

        secure_filename = f"{uuid.uuid4().hex}{detected_ext}"
        destination_path = os.path.join(UPLOADS_DIR, secure_filename)

        with open(destination_path, "wb") as f:
            f.write(file_bytes)

        file_url = f"/uploads/{secure_filename}"
        return self.send_json({"success": True, "url": file_url}, status=201)


def run_server(port=8000, host="127.0.0.1"):
    server_address = (host, port)
    httpd = ThreadingHTTPServer(server_address, InnovaRequestHandler)
    print(f"================================================================")
    print(f"  INNOVA Web & Admin Server Activo")
    print(f"  Tienda Pública:        http://{host}:{port}/")
    print(f"  Panel de Administración: http://{host}:{port}/admin")
    print(f"================================================================")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Servidor detenido por el usuario.")
        httpd.server_close()


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    host = os.environ.get("HOST", "127.0.0.1")
    run_server(port=port, host=host)
