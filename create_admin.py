"""
INNOVA Admin User Provisioning Tool
Creates or updates an administrator account safely via CLI.
Passwords are never stored in plain text.
"""

import sys
import os
import argparse
import getpass
import re
import secrets
import string

# Ensure project directory is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import db


def validate_email(email: str) -> bool:
    return bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))


def validate_username(username: str) -> bool:
    return bool(re.match(r"^[a-zA-Z0-9_\-\.]{3,30}$", username))


def validate_password(password: str) -> bool:
    return len(password) >= 8


def generate_secure_password(length=14) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    while True:
        pwd = "".join(secrets.choice(alphabet) for _ in range(length))
        if (any(c.islower() for c in pwd)
                and any(c.isupper() for c in pwd)
                and any(c.isdigit() for c in pwd)
                and any(c in "!@#$%^&*" for c in pwd)):
            return pwd


def create_or_update_admin(username: str, email: str, password: str) -> bool:
    db.init_db()
    conn = db.get_db()
    cur = conn.cursor()

    cur.execute("SELECT id, username, email FROM users WHERE username = ? OR email = ?", (username, email))
    existing = cur.fetchone()

    salt_hex, key_hex = db.hash_password(password)

    with conn:
        if existing:
            conn.execute("""
                UPDATE users
                SET username = ?, email = ?, password_hash = ?, salt = ?, role = 'admin'
                WHERE id = ?
            """, (username, email, key_hex, salt_hex, existing["id"]))
            print(f"[OK] Usuario administrador '{username}' ({email}) actualizado exitosamente.")
        else:
            conn.execute("""
                INSERT INTO users (username, email, password_hash, salt, role)
                VALUES (?, ?, ?, ?, 'admin')
            """, (username, email, key_hex, salt_hex))
            print(f"[OK] Usuario administrador '{username}' ({email}) creado exitosamente.")
    conn.close()
    return True


def main():
    parser = argparse.ArgumentParser(description="Crear o actualizar un usuario administrador en INNOVA")
    parser.add_argument("--username", "-u", help="Nombre de usuario del administrador")
    parser.add_argument("--email", "-e", help="Correo electrónico del administrador")
    parser.add_argument("--password", "-p", help="Contraseña del administrador (opcional, si no se especifica se solicitará)")
    parser.add_argument("--generate-password", action="store_true", help="Generar una contraseña segura aleatoria")

    args = parser.parse_args()

    username = args.username
    email = args.email
    password = args.password

    # Interactive prompts if arguments not supplied
    if not username:
        try:
            username = input("Nombre de usuario (ej: admin): ").strip()
        except EOFError:
            username = "admin"

    if not email:
        try:
            email = input("Correo electrónico (ej: admin@innova.com): ").strip()
        except EOFError:
            email = "admin@innova.com"

    if not validate_username(username):
        print("[ERROR] El nombre de usuario debe tener entre 3 y 30 caracteres (letras, números, '.', '_', '-')")
        sys.exit(1)

    if not validate_email(email):
        print("[ERROR] El correo electrónico no tiene un formato válido.")
        sys.exit(1)

    if args.generate_password:
        password = generate_secure_password()
        print(f"\n[INFO] Contraseña segura generada automáticamente: {password}\n")
    elif not password:
        try:
            password = getpass.getpass("Contraseña (mínimo 8 caracteres): ")
            confirm = getpass.getpass("Confirmar contraseña: ")
            if password != confirm:
                print("[ERROR] Las contraseñas no coinciden.")
                sys.exit(1)
        except (EOFError, io.UnsupportedOperation):
            password = generate_secure_password()
            print(f"\n[INFO] Contraseña generada automáticamente: {password}\n")

    if not validate_password(password):
        print("[ERROR] La contraseña debe tener al menos 8 caracteres.")
        sys.exit(1)

    create_or_update_admin(username, email, password)


if __name__ == "__main__":
    main()

