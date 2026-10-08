# -*- coding: utf-8 -*-
"""Genera el par de llaves VAPID de los avisos y lo deja en config.json.

Uso:
    python generar_vapid.py            # sólo si faltan las llaves
    python generar_vapid.py --forzar   # las regenera (las suscripciones
                                       # existentes dejarán de servir)

La pública (`vapid_publica`) viaja dentro de la página; la privada
(`vapid_privada`) nunca sale de config.json, que está en .gitignore.
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from py_vapid import Vapid02

CONFIG = Path(__file__).resolve().parent / "config.json"


def _b64url(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).decode("ascii").rstrip("=")


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Genera las llaves VAPID.")
    parser.add_argument("--forzar", action="store_true",
                        help="regenera aunque ya existan (rompe las suscripciones)")
    args = parser.parse_args(argv)

    try:
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"No se pudo leer config.json: {exc}")
        return 1

    avisos = config.get("avisos") or {}
    if avisos.get("vapid_privada") and not args.forzar:
        print("Ya hay llaves VAPID en config.json (usa --forzar para regenerar).")
        return 0

    v = Vapid02()
    v.generate_keys()
    clave = v.private_key
    privada = _b64url(clave.private_numbers().private_value.to_bytes(32, "big"))
    publica = _b64url(clave.public_key().public_bytes(
        Encoding.X962,          # punto sin comprimir (04||X||Y)
        PublicFormat.UncompressedPoint))

    config["avisos"] = dict(avisos, vapid_publica=publica,
                            vapid_privada=privada,
                            sujetos=str(avisos.get("sujetos")
                                       or "https://edufacil.cl"))
    CONFIG.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8")
    print("Llaves VAPID escritas en config.json")
    print(f"  vapid_publica: {publica[:24]}…")
    print("  (si regeneraste con --forzar, vuelve a generar la página: "
          "python main.py)")
    return 0


if __name__ == "__main__":
    sys.exit(principal())
