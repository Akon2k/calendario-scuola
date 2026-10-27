# -*- coding: utf-8 -*-
"""Prepara secretos LOCALES para desplegar avisos inmediatos. No envía nada.

Uso: python preparar_push.py
Escribe sólo en logs/push-inmediato/ (ignorado por git). No imprime secretos.
"""
from __future__ import annotations

import json
import re
import secrets
from pathlib import Path
from urllib.parse import urlparse

RAIZ = Path(__file__).resolve().parent


def preparar(raiz: Path = RAIZ) -> Path:
    config = json.loads((raiz / "config.json").read_text(encoding="utf-8"))
    avisos = config.get("avisos") or {}
    supabase = config.get("supabase") or {}
    url = str(supabase.get("url") or "").rstrip("/")
    if not re.fullmatch(r"https://[a-z0-9]+\.supabase\.co", url):
        raise ValueError("URL del proyecto Supabase no válida")
    publica = str(avisos.get("vapid_publica") or "").strip()
    privada = str(avisos.get("vapid_privada") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{87}", publica) or not re.fullmatch(
            r"[A-Za-z0-9_-]{43}", privada):
        raise ValueError("Se necesitan las mismas claves VAPID base64url que usa la web")
    sujeto = str(avisos.get("sujetos") or "").strip()
    if not sujeto.startswith(("mailto:", "https://")):
        raise ValueError("Configura avisos.sujetos con mailto: o https://")
    repo = str((config.get("github") or {}).get("repo") or "calendario-scuola")
    # Este proyecto tiene una URL fija; no adivinar otra cuenta de GitHub.
    pagina = "https://akon2k.github.io/" + repo + "/"
    if not re.fullmatch(r"[\w.-]+", repo) or urlparse(pagina).scheme != "https":
        raise ValueError("Nombre de repositorio no válido")
    if any("\n" in v or "\r" in v for v in (sujeto, publica, privada)):
        raise ValueError("Los secretos no deben contener saltos de línea")

    destino = raiz / "logs" / "push-inmediato"
    destino.mkdir(parents=True, exist_ok=True)
    env = destino / "servidor.env"
    if env.exists():
        # No rotar el secreto accidentalmente al ejecutar la preparación otra vez.
        raise FileExistsError("Ya existe logs/push-inmediato/servidor.env; no se sobrescribe")
    secreto = secrets.token_urlsafe(48)
    valores = {"VAPID_PUBLIC_KEY": publica, "VAPID_PRIVATE_KEY": privada,
               "VAPID_SUBJECT": sujeto, "PUSH_SITE_URL": pagina,
               "PUSH_WEBHOOK_SECRET": secreto}
    env.write_text("".join(k + "=" + json.dumps(v) + "\n" for k, v in valores.items()),
                   encoding="utf-8")
    def literal(valor: str) -> str:
        return "'" + valor.replace("'", "''") + "'"
    # Sólo crea/actualiza los secretos del webhook. NO activa avisos.
    sql = "-- PRIVADO: no compartir ni subir a GitHub.\nbegin;\n"
    for nombre, valor in (("push_ediciones_secret", secreto),
                          ("push_ediciones_url", url + "/functions/v1/avisos-ediciones")):
        sql += ("do $$ declare sid uuid; begin\n"
                " select id into sid from vault.secrets where name = " + literal(nombre) + ";\n"
                " if sid is null then perform vault.create_secret(" + literal(valor)
                + ", " + literal(nombre) + ");\n"
                " else perform vault.update_secret(sid, " + literal(valor)
                + "); end if;\nend $$;\n")
    sql += "commit;\n"
    (destino / "configurar_webhook.sql").write_text(sql, encoding="utf-8")
    return destino


if __name__ == "__main__":
    try:
        preparar()
        print("Preparado en logs/push-inmediato/. Archivos PRIVADOS, no compartir.")
        print("No se ha desplegado ni activado nada. Sigue docs/avisos_inmediatos.md.")
    except (ValueError, OSError, KeyError):
        raise SystemExit("No se pudo preparar (configuración inválida o archivos ya existentes).")
