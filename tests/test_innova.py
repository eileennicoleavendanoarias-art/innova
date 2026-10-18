"""
Comprehensive Automated Test Suite for INNOVA E-Commerce System
Validates Logo fix, Database, Security, Auth, CRUD, Inventory, Promotions, and APIs.
"""

import unittest
import sys
import os
import json
import sqlite3
import tempfile
import threading
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from http.cookies import SimpleCookie

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import db
import server


class TestInnovaSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize DB in project
        db.init_db()

        # Start background server on test port
        cls.test_port = 8899
        cls.server_thread = threading.Thread(
            target=server.run_server,
            kwargs={"port": cls.test_port, "host": "127.0.0.1"},
            daemon=True
        )
        cls.server_thread.start()
        time.sleep(1.0)  # Allow server to bind and start

        cls.base_url = f"http://127.0.0.1:{cls.test_port}"

        # Create test admin user in database
        cls.admin_username = "testadmin"
        cls.admin_email = "testadmin@innova.com"
        cls.admin_password = "SecretPassword123!"

        conn = db.get_db()
        salt_hex, key_hex = db.hash_password(cls.admin_password)
        with conn:
            conn.execute("""
                INSERT OR REPLACE INTO users (username, email, password_hash, salt, role)
                VALUES (?, ?, ?, ?, 'admin')
            """, (cls.admin_username, cls.admin_email, key_hex, salt_hex))
        conn.close()

    def setUp(self):
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM login_attempts")
        conn.close()

    def request(self, method, path, data=None, cookie=None, headers=None):
        url = f"{self.base_url}{path}"
        req_headers = headers or {}
        body = None

        if data is not None:
            if isinstance(data, (dict, list)):
                body = json.dumps(data).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
            else:
                body = data

        if cookie:
            req_headers["Cookie"] = cookie

        req = Request(url, data=body, headers=req_headers, method=method)
        try:
            with urlopen(req) as resp:
                resp_body = resp.read().decode("utf-8")
                set_cookie = resp.headers.get("Set-Cookie")
                try:
                    json_data = json.loads(resp_body)
                except Exception:
                    json_data = resp_body
                return resp.status, json_data, set_cookie
        except HTTPError as e:
            err_body = e.read().decode("utf-8")
            try:
                json_data = json.loads(err_body)
            except Exception:
                json_data = err_body
            return e.code, json_data, None

    def get_admin_session(self):
        status, data, cookie = self.request(
            "POST", "/api/auth/login",
            {"identifier": self.admin_username, "password": self.admin_password}
        )
        self.assertEqual(status, 200)
        self.assertTrue(data.get("success"))
        self.assertIn("innova_session=", cookie)
        # Extract clean cookie value
        session_token = cookie.split(";")[0]
        return session_token

    # =========================================================
    # 1. LOGO INTEGRITY TESTS
    # =========================================================
    def test_logo_dot_eliminated_from_html_and_css(self):
        """Verifies that the stray dot next to the logo is removed everywhere."""
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        index_html_path = os.path.join(base_dir, "index.html")
        styles_css_path = os.path.join(base_dir, "styles.css")

        import re
        with open(index_html_path, "r", encoding="utf-8") as f:
            html = f.read()

        self.assertNotIn('<span class="wordmark-dot">.</span>', html, "Wordmark dot span must be removed from index.html")
        wordmarks = re.findall(r'<a class="wordmark"[^>]*>(.*?)</a>', html, flags=re.DOTALL)
        self.assertGreaterEqual(len(wordmarks), 2, "Header and footer wordmarks must be present")
        for wm in wordmarks:
            self.assertNotIn("INNOVA.", wm, "Wordmark should not have a dot after INNOVA")
            self.assertIn("INNOVA", wm, "Wordmark must contain brand name INNOVA")

        with open(styles_css_path, "r", encoding="utf-8") as f:
            css = f.read()

        self.assertNotIn(".wordmark-dot", css, "Unused .wordmark-dot selector should be removed from styles.css")

        # Verify logo image file exists
        logo_path = os.path.join(base_dir, "assets", "innova-mark.png")
        self.assertTrue(os.path.exists(logo_path), "assets/innova-mark.png must exist")

    # =========================================================
    # 2. DATABASE & PASSWORD HASHING
    # =========================================================
    def test_password_hashing_security(self):
        """Verifies PBKDF2 hashing with salt behaves securely."""
        pwd = "ComplexPassword2026!"
        salt1, key1 = db.hash_password(pwd)
        salt2, key2 = db.hash_password(pwd)

        # Unique salts generate unique hashes
        self.assertNotEqual(salt1, salt2)
        self.assertNotEqual(key1, key2)

        # Verification succeeds with matching password
        self.assertTrue(db.verify_password(pwd, salt1, key1))
        # Verification fails with wrong password
        self.assertFalse(db.verify_password("WrongPassword", salt1, key1))

    def test_database_tables_and_seeds(self):
        """Verifies database schema integrity and default seeds."""
        conn = db.get_db()
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) as c FROM products")
        count = cur.fetchone()["c"]
        self.assertGreaterEqual(count, 8, "Database should contain at least the 8 initial catalog products")

        cur.execute("SELECT COUNT(*) as c FROM categories")
        cat_count = cur.fetchone()["c"]
        self.assertGreaterEqual(cat_count, 4, "Database should contain initial categories")
        conn.close()

    # =========================================================
    # 3. AUTHENTICATION & SESSIONS
    # =========================================================
    def test_auth_flow_login_me_logout(self):
        """Tests full auth lifecycle: login, me, and logout."""
        # 1. Me without cookie -> 401
        status, data, _ = self.request("GET", "/api/auth/me")
        self.assertEqual(status, 401)

        # 2. Login with correct credentials -> 200 + cookie
        session_cookie = self.get_admin_session()

        # 3. Me with session cookie -> 200 + user info
        status, data, _ = self.request("GET", "/api/auth/me", cookie=session_cookie)
        self.assertEqual(status, 200)
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data["user"]["username"], self.admin_username)

        # 4. Logout -> 200 + cleared cookie
        status, data, logout_cookie = self.request("POST", "/api/auth/logout", cookie=session_cookie)
        self.assertEqual(status, 200)
        self.assertIn("Max-Age=0", logout_cookie)

        # 5. Subsequent me call -> 401
        status, _, _ = self.request("GET", "/api/auth/me", cookie=session_cookie)
        self.assertEqual(status, 401)

    def test_auth_brute_force_rate_limit(self):
        """Verifies rate limiting triggers after repeated failures."""
        dummy_ip_user = "brute_force_test_user"
        for i in range(5):
            self.request("POST", "/api/auth/login", {"identifier": dummy_ip_user, "password": "wrong"})

        # 6th attempt should be blocked by rate limiter
        status, data, _ = self.request("POST", "/api/auth/login", {"identifier": dummy_ip_user, "password": "wrong"})
        self.assertEqual(status, 429)
        self.assertIn("seguridad", data.get("error", "").lower())

        # Clean up login_attempts so other tests from 127.0.0.1 are not rate-limited
        conn = db.get_db()
        with conn:
            conn.execute("DELETE FROM login_attempts")
        conn.close()

    # =========================================================
    # 4. PRODUCT CRUD & VALIDATION
    # =========================================================
    def test_product_crud_and_validation(self):
        """Tests product creation, validation constraints, updating, and deletion."""
        session = self.get_admin_session()

        # 1. Validation: negative price rejected
        status, data, _ = self.request("POST", "/api/products", {
            "name": "Invalid Product",
            "price": -10,
            "stock": 5
        }, cookie=session)
        self.assertEqual(status, 400)

        # 2. Validation: promo price >= regular price rejected
        status, data, _ = self.request("POST", "/api/products", {
            "name": "Invalid Promo",
            "price": 100,
            "promo_price": 150,
            "stock": 5
        }, cookie=session)
        self.assertEqual(status, 400)

        # 3. Create valid product
        test_prod_id = f"test-gadget-{int(time.time())}"
        status, data, _ = self.request("POST", "/api/products", {
            "id": test_prod_id,
            "name": "Test Gadget Ultra",
            "price": 500,
            "promo_price": 400,
            "stock": 10,
            "sku": "TEST-SKU-01",
            "status": "active",
            "featured": True,
            "short_description": "A wonderful test device",
            "specs": ["Bluetooth 5.3", "IP68"],
            "images": ["/assets/innova-mark.png"]
        }, cookie=session)
        self.assertEqual(status, 201)

        # 4. Fetch details
        status, data, _ = self.request("GET", f"/api/products/{test_prod_id}")
        self.assertEqual(status, 200)
        prod = data["product"]
        self.assertEqual(prod["name"], "Test Gadget Ultra")
        self.assertEqual(prod["effective_price"], 400)
        self.assertEqual(prod["discount_percent"], 20)
        self.assertTrue(prod["has_discount"])
        self.assertEqual(prod["stock"], 10)

        # 5. Update product
        status, data, _ = self.request("PUT", f"/api/products/{test_prod_id}", {
            "name": "Test Gadget Ultra Updated",
            "price": 550,
            "stock": 12
        }, cookie=session)
        self.assertEqual(status, 200)

        # 6. Delete product
        status, data, _ = self.request("DELETE", f"/api/products/{test_prod_id}", cookie=session)
        self.assertEqual(status, 200)

        # Confirm deleted
        status, _, _ = self.request("GET", f"/api/products/{test_prod_id}")
        self.assertEqual(status, 404)

    # =========================================================
    # 5. INVENTORY & STOCK MOVEMENTS AUDIT
    # =========================================================
    def test_inventory_adjustments_and_movements(self):
        """Tests inventory adjustments (+, -, set), prevention of negative stock, and audit logs."""
        session = self.get_admin_session()

        # Create a test item with 10 units
        inv_prod_id = f"test-inv-{int(time.time())}"
        self.request("POST", "/api/products", {
            "id": inv_prod_id,
            "name": "Inventory Test Item",
            "price": 100,
            "stock": 10
        }, cookie=session)

        # 1. Add 5 units
        status, data, _ = self.request("POST", "/api/inventory/adjust", {
            "product_id": inv_prod_id,
            "action": "add",
            "quantity": 5,
            "reason": "Entrada de prueba de almacén"
        }, cookie=session)
        self.assertEqual(status, 200)
        self.assertEqual(data["new_stock"], 15)

        # 2. Attempt to subtract more than available (15 available, subtract 20) -> should fail
        status, data, _ = self.request("POST", "/api/inventory/adjust", {
            "product_id": inv_prod_id,
            "action": "subtract",
            "quantity": 20,
            "reason": "Prueba de sobreventa inválida"
        }, cookie=session)
        self.assertEqual(status, 400)

        # 3. Set stock to 0 (Mark as Out of Stock)
        status, data, _ = self.request("POST", "/api/inventory/adjust", {
            "product_id": inv_prod_id,
            "action": "set",
            "quantity": 0,
            "reason": "Agotado por venta total"
        }, cookie=session)
        self.assertEqual(status, 200)
        self.assertEqual(data["new_stock"], 0)

        # 4. Check product stock status on public API
        status, data, _ = self.request("GET", f"/api/products/{inv_prod_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["product"]["stock_status"], "out_of_stock")
        self.assertFalse(data["product"]["is_available"])

        # 5. Verify movements audit log
        status, data, _ = self.request("GET", f"/api/inventory/movements?product_id={inv_prod_id}", cookie=session)
        self.assertEqual(status, 200)
        movements = data["movements"]
        self.assertGreaterEqual(len(movements), 3, "Initial creation + add 5 + set 0 = 3 movements")

        # Cleanup
        self.request("DELETE", f"/api/products/{inv_prod_id}", cookie=session)

    # =========================================================
    # 6. PROMOTIONS & AUTOMATIC DISCOUNT CALCULATION
    # =========================================================
    def test_promotions_and_pricing_rules(self):
        """Tests promotion creation, percentage/fixed calculations, and date enforcement."""
        session = self.get_admin_session()

        # Create product priced at 200
        promo_prod_id = f"test-promo-{int(time.time())}"
        self.request("POST", "/api/products", {
            "id": promo_prod_id,
            "name": "Promotional Product",
            "price": 200,
            "stock": 8
        }, cookie=session)

        # 1. Create active 25% discount promotion
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())
        future = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() + 86400))
        status, data, _ = self.request("POST", "/api/promotions", {
            "name": "Flash 25% Off",
            "discount_type": "percent",
            "discount_value": 25,
            "target_type": "product",
            "target_id": promo_prod_id,
            "starts_at": now,
            "ends_at": future,
            "is_active": True
        }, cookie=session)
        self.assertEqual(status, 201)
        promo_id = data["promotion_id"]

        # 2. Check that effective price reflects 25% off (200 - 25% = 150)
        status, data, _ = self.request("GET", f"/api/products/{promo_prod_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["product"]["effective_price"], 150)
        self.assertEqual(data["product"]["discount_percent"], 25)
        self.assertTrue(data["product"]["has_discount"])

        # 3. Test expired promotion does NOT apply
        past_start = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 86400 * 2))
        past_end = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(time.time() - 86400))
        self.request("PUT", f"/api/promotions/{promo_id}", {
            "name": "Expired Sale",
            "discount_type": "percent",
            "discount_value": 50,
            "target_type": "product",
            "target_id": promo_prod_id,
            "starts_at": past_start,
            "ends_at": past_end,
            "is_active": True
        }, cookie=session)

        status, data, _ = self.request("GET", f"/api/products/{promo_prod_id}")
        self.assertEqual(status, 200)
        self.assertEqual(data["product"]["effective_price"], 200, "Expired promotion must not apply")
        self.assertFalse(data["product"]["has_discount"])

        # Cleanup
        self.request("DELETE", f"/api/promotions/{promo_id}", cookie=session)
        self.request("DELETE", f"/api/products/{promo_prod_id}", cookie=session)

    # =========================================================
    # 7. CATEGORY INTEGRITY
    # =========================================================
    def test_category_deletion_protection(self):
        """Verifies that a category with assigned products cannot be deleted."""
        session = self.get_admin_session()

        # Get existing category with products (e.g. Celulares)
        status, data, _ = self.request("GET", "/api/categories")
        self.assertEqual(status, 200)
        cat_with_products = next((c for c in data["categories"] if c["product_count"] > 0), None)
        self.assertIsNotNone(cat_with_products)

        # Attempt deletion -> should be blocked
        status, data, _ = self.request("DELETE", f"/api/categories/{cat_with_products['id']}", cookie=session)
        self.assertEqual(status, 400)
        self.assertIn("asociados", data.get("error", "").lower())

    # =========================================================
    # 8. SECURE FILE UPLOAD
    # =========================================================
    def test_file_upload_security(self):
        """Tests that only valid image formats are accepted and malicious files are rejected."""
        session = self.get_admin_session()

        # 1. Reject non-image text content
        boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
        fake_file = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="test.txt"\r\n'
            f"Content-Type: text/plain\r\n\r\n"
            f"Hello world, I am not an image\r\n"
            f"--{boundary}--\r\n"
        ).encode("utf-8")

        status, data, _ = self.request(
            "POST", "/api/upload",
            data=fake_file,
            cookie=session,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        self.assertEqual(status, 400)
        self.assertIn("legítimos", data.get("error", "").lower())

        # 2. Accept valid PNG with magic bytes
        png_magic = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15c4"
        valid_file = (
            f"--{boundary}\r\n".encode() +
            b'Content-Disposition: form-data; name="file"; filename="valid.png"\r\n' +
            b"Content-Type: image/png\r\n\r\n" +
            png_magic +
            f"\r\n--{boundary}--\r\n".encode()
        )

        status, data, _ = self.request(
            "POST", "/api/upload",
            data=valid_file,
            cookie=session,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
        )
        self.assertEqual(status, 201)
        self.assertTrue(data.get("url").startswith("/uploads/"))
        self.assertTrue(data.get("url").endswith(".png"))


    # =========================================================
    # 9. CUSTOMER AUTHENTICATION & ROLE ISOLATION
    # =========================================================
    def test_customer_registration_and_role_escalation_blocked(self):
        """Verifies customer registration and ensures role escalation to admin is blocked."""
        # Attempt to register with role = 'admin'
        reg_payload = {
            "email": "customer_attacker@innova.com",
            "password": "CustomerSecurePass123!",
            "full_name": "Test Cliente",
            "role": "admin",
            "notification_prefs": {"promos": True, "new_products": True, "stock_alerts": False}
        }
        status, data, cookie = self.request("POST", "/api/auth/register", reg_payload)
        self.assertEqual(status, 201)
        self.assertEqual(data["user"]["role"], "cliente", "Role escalation must be completely neutralized to 'cliente'")
        self.assertEqual(data["user"]["full_name"], "Test Cliente")
        self.assertIsNotNone(cookie, "Registration must return active session cookie")

        # Verify welcome notification exists
        status, notif_data, _ = self.request("GET", "/api/customer/notifications", cookie=cookie)
        self.assertEqual(status, 200)
        self.assertTrue(len(notif_data["notifications"]) >= 1)
        self.assertIn("Bienvenido", notif_data["notifications"][0]["title"])

    def test_customer_role_enforcement_on_admin_endpoints(self):
        """Strictly tests that a customer role receives 403 Forbidden on all administrative endpoints."""
        # Register standard customer
        cust_payload = {
            "email": "standard_customer@innova.com",
            "password": "CustomerSecurePass123!",
            "full_name": "Cliente Estandar"
        }
        status, data, cust_session = self.request("POST", "/api/auth/register", cust_payload)
        self.assertEqual(status, 201)

        # 1. Attempt to create product as customer -> 403 Forbidden
        status, data, _ = self.request("POST", "/api/products", {
            "name": "Hacked Product",
            "price": 100
        }, cookie=cust_session)
        self.assertEqual(status, 403, "Non-admin must receive 403 on product creation")

        # 2. Attempt to adjust inventory as customer -> 403 Forbidden
        status, data, _ = self.request("POST", "/api/inventory/adjust", {
            "product_id": "test",
            "action": "add",
            "quantity": 50,
            "reason": "Unauthorized"
        }, cookie=cust_session)
        self.assertEqual(status, 403, "Non-admin must receive 403 on inventory adjustment")

        # 3. Attempt to duplicate product as customer -> 403 Forbidden
        status, data, _ = self.request("POST", "/api/products/auriculares-pro/duplicate", cookie=cust_session)
        self.assertEqual(status, 403, "Non-admin must receive 403 on product duplication")

        # 4. Attempt to broadcast notifications as customer -> 403 Forbidden
        status, data, _ = self.request("POST", "/api/admin/notifications", {
            "title": "Spam",
            "message": "Spam"
        }, cookie=cust_session)
        self.assertEqual(status, 403, "Non-admin must receive 403 on broadcast notifications")

    # =========================================================
    # 10. CUSTOMER FAVORITES, ACTIVITY & GDPR
    # =========================================================
    def test_customer_favorites_and_activity_lifecycle(self):
        """Tests favorites toggling, activity recording, and clearing."""
        cust_payload = {
            "email": "fav_user@innova.com",
            "password": "CustomerSecurePass123!",
            "full_name": "Favorite User"
        }
        _, _, session = self.request("POST", "/api/auth/register", cust_payload)

        # 1. Toggle favorite on product
        status, data, _ = self.request("POST", "/api/customer/favorites/toggle", {"product_id": "auriculares-pro"}, cookie=session)
        self.assertEqual(status, 200)
        self.assertEqual(data["action"], "added")

        # 2. Retrieve favorites
        status, data, _ = self.request("GET", "/api/customer/favorites", cookie=session)
        self.assertEqual(status, 200)
        fav_ids = [f["product_id"] for f in data["favorites"]]
        self.assertIn("auriculares-pro", fav_ids)

        # 3. Log customer activity
        status, data, _ = self.request("POST", "/api/customer/activity", {
            "event_type": "view_product",
            "product_id": "auriculares-pro"
        }, cookie=session)
        self.assertEqual(status, 200)

        status, data, _ = self.request("GET", "/api/customer/activity", cookie=session)
        self.assertEqual(status, 200)
        self.assertTrue(len(data["activity"]) >= 1)

        # 4. Clear activity
        status, data, _ = self.request("DELETE", "/api/customer/activity", cookie=session)
        self.assertEqual(status, 200)
        status, data, _ = self.request("GET", "/api/customer/activity", cookie=session)
        self.assertEqual(len(data["activity"]), 0)

        # 5. Untoggle favorite
        status, data, _ = self.request("POST", "/api/customer/favorites/toggle", {"product_id": "auriculares-pro"}, cookie=session)
        self.assertEqual(status, 200)
        self.assertEqual(data["action"], "removed")

    # =========================================================
    # 11. RECOMMENDATIONS & OUT-OF-STOCK FILTERING
    # =========================================================
    def test_recommendations_availability_and_reasons(self):
        """Verifies recommendation algorithm strictly excludes out-of-stock items and returns clear reasons."""
        admin_session = self.get_admin_session()

        # Create an out-of-stock product
        sold_out_id = "test-sold-out-rec"
        self.request("POST", "/api/products", {
            "id": sold_out_id,
            "name": "Sold Out Gadget",
            "price": 100,
            "stock": 0,
            "category_id": 1,
            "status": "active"
        }, cookie=admin_session)

        # Query recommendations for customer
        cust_payload = {
            "email": "rec_shopper@innova.com",
            "password": "CustomerSecurePass123!",
            "full_name": "Shopper Rec"
        }
        _, _, session = self.request("POST", "/api/auth/register", cust_payload)

        status, data, _ = self.request("GET", "/api/customer/recommendations", cookie=session)
        self.assertEqual(status, 200)
        recs = data["recommendations"]
        self.assertTrue(len(recs) > 0)

        # Ensure no out-of-stock items are ever recommended
        rec_ids = [r["id"] for r in recs]
        self.assertNotIn(sold_out_id, rec_ids, "Out-of-stock products must NEVER be recommended to customers")

        for r in recs:
            self.assertTrue(r["stock"] > 0)
            self.assertIn("recommendation_reason", r)
            self.assertTrue(len(r["recommendation_reason"]) > 0)

        # Cleanup test product
        self.request("DELETE", f"/api/products/{sold_out_id}", cookie=admin_session)

    # =========================================================
    # 12. PASSWORD RESET WORKFLOW
    # =========================================================
    def test_password_reset_workflow(self):
        """Tests tokenized password reset end-to-end."""
        user_email = "reset_user@innova.com"
        old_pass = "OldPassword123!"
        new_pass = "BrandNewPassword123!"

        # Register user
        self.request("POST", "/api/auth/register", {
            "email": user_email,
            "password": old_pass,
            "full_name": "Reset User"
        })

        # Request reset
        status, data, _ = self.request("POST", "/api/auth/password-reset/request", {"email": user_email})
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])
        token = data.get("token")
        self.assertIsNotNone(token)

        # Confirm reset
        status, data, _ = self.request("POST", "/api/auth/password-reset/confirm", {
            "token": token,
            "new_password": new_pass
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

        # Old password must fail
        status, data, _ = self.request("POST", "/api/auth/login", {
            "identifier": user_email,
            "password": old_pass
        })
        self.assertEqual(status, 401)

        # New password must succeed
        status, data, _ = self.request("POST", "/api/auth/login", {
            "identifier": user_email,
            "password": new_pass
        })
        self.assertEqual(status, 200)
        self.assertTrue(data["success"])

    # =========================================================
    # 13. PRODUCT DUPLICATION (ADMIN)
    # =========================================================
    def test_product_duplication_admin(self):
        """Verifies admin product duplication creates an editable draft copy."""
        admin_session = self.get_admin_session()

        # Duplicate existing product 'auriculares-pro'
        status, data, _ = self.request("POST", "/api/products/auriculares-pro/duplicate", cookie=admin_session)
        self.assertEqual(status, 201)
        self.assertTrue(data["success"])

        dup = data["duplicated_product"]
        self.assertEqual(dup["status"], "draft", "Duplicated product must default to draft")
        self.assertTrue("(Copia)" in dup["name"])
        self.assertTrue(dup["id"].endswith("-copy"))

        # Cleanup duplicate
        self.request("DELETE", f"/api/products/{dup['id']}", cookie=admin_session)

    # =========================================================
    # 14. TARGETED NOTIFICATION BROADCAST WITH PREFERENCES
    # =========================================================
    def test_admin_notification_broadcast_respects_preferences(self):
        """Tests that customer communication preferences are strictly respected during campaign dispatches."""
        admin_session = self.get_admin_session()

        # Customer A: accepts promos
        email_a = "promo_lover@innova.com"
        _, _, session_a = self.request("POST", "/api/auth/register", {
            "email": email_a,
            "password": "Password123!",
            "full_name": "Lover",
            "notification_prefs": {"promos": True, "new_products": True, "stock_alerts": True}
        })

        # Customer B: rejects promos
        email_b = "promo_hater@innova.com"
        _, _, session_b = self.request("POST", "/api/auth/register", {
            "email": email_b,
            "password": "Password123!",
            "full_name": "Hater",
            "notification_prefs": {"promos": False, "new_products": True, "stock_alerts": True}
        })

        # Admin broadcasts campaign targeted to 'promos'
        unique_title = f"Exclusive Flash Promo {int(time.time())}"
        status, data, _ = self.request("POST", "/api/admin/notifications", {
            "target": "promos",
            "type": "promo",
            "title": unique_title,
            "message": "Huge discounts today only!"
        }, cookie=admin_session)
        self.assertEqual(status, 201)

        # Customer A must have received it
        status, data_a, _ = self.request("GET", "/api/customer/notifications", cookie=session_a)
        titles_a = [n["title"] for n in data_a["notifications"]]
        self.assertIn(unique_title, titles_a)

        # Customer B must NOT have received it
        status, data_b, _ = self.request("GET", "/api/customer/notifications", cookie=session_b)
        titles_b = [n["title"] for n in data_b["notifications"]]
        self.assertNotIn(unique_title, titles_b, "Customer with promos=False must NOT receive promo campaigns")


if __name__ == "__main__":
    unittest.main()

