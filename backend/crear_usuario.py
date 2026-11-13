"""Crea un usuario o cambia su contraseña en MongoDB.

Uso (en la carpeta backend, con el entorno virtual activado):
    python crear_usuario.py admin
    python crear_usuario.py maria --nombre "María Pérez" --rol Operador
Si el usuario ya existe, solo se actualiza su contraseña.
"""
import argparse
import getpass
import sys

from app import dbschema, mongo, repository


def main() -> int:
    ap = argparse.ArgumentParser(description="Crear usuario o cambiar contraseña")
    ap.add_argument("usuario")
    ap.add_argument("--nombre", help="Nombre completo")
    ap.add_argument("--rol", default="Administrador", help="Administrador, Despachador, Supervisor, Usuario…")
    args = ap.parse_args()

    pw = getpass.getpass("Contraseña nueva: ")
    if len(pw) < 6:
        print("La contraseña debe tener al menos 6 caracteres.")
        return 1
    if pw != getpass.getpass("Repite la contraseña: "):
        print("Las contraseñas no coinciden.")
        return 1

    try:
        mongo.connect()
        dbschema.ensure_schema()
    except RuntimeError as exc:
        print(f"\n{exc}")
        return 1

    res = repository.upsert_user(args.usuario, pw, args.nombre, args.rol)
    print(f"\nUsuario '{res['username']}' {'creado' if res['created'] else 'actualizado'}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
