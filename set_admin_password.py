"""Generates an ADMIN_PASSWORD_HASH value to put in .env.

Run this once per deployment instead of hardcoding a password in the code:

    python set_admin_password.py
"""
import getpass

from werkzeug.security import generate_password_hash


def main():
    password = getpass.getpass("Nueva contraseña de administrador: ")
    confirm = getpass.getpass("Confirmar contraseña: ")
    if password != confirm:
        print("Las contraseñas no coinciden.")
        return
    if len(password) < 6:
        print("La contraseña debe tener al menos 6 caracteres.")
        return

    print("\nAgrega esta línea a tu archivo .env:\n")
    print(f"ADMIN_PASSWORD_HASH={generate_password_hash(password)}")


if __name__ == '__main__':
    main()
