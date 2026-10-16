"""Genera SQL y una clave de escritura local, sin tocar Supabase ni config.json."""
from hashlib import sha256
from pathlib import Path
import secrets


def main() -> None:
    raiz = Path(__file__).resolve().parent.parent
    clave_path = raiz / "logs" / "botscuola_clave.txt"
    clave_path.parent.mkdir(exist_ok=True)
    if not clave_path.exists():
        # No sobrescribir una clave existente: repetir no la rota por accidente.
        try:
            with clave_path.open("x", encoding="utf-8") as archivo:
                archivo.write(secrets.token_hex(32) + "\n")
        except FileExistsError:
            pass
    clave = clave_path.read_text(encoding="utf-8").strip()
    if len(clave) != 64 or any(c not in "0123456789abcdef" for c in clave):
        raise ValueError("Clave local no valida; no se modifica ni se imprime.")
    plantilla = (raiz / "botscuola" / "comunicados.sql").read_text(encoding="utf-8")
    destino = raiz / "salida" / "comunicados.sql"
    destino.parent.mkdir(exist_ok=True)
    destino.write_text(plantilla.replace("{{SHA256_CLAVE}}", sha256(clave.encode()).hexdigest()),
                       encoding="utf-8")
    print(f"SQL listo para el editor de Supabase: {destino}")
    print(f"Clave privada para BOTSCUOLA_CLAVE: {clave_path}")
    print("No se ha conectado a Supabase ni publicado nada. No compartas el archivo de la clave.")


if __name__ == "__main__":
    main()
