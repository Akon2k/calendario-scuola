# -*- coding: utf-8 -*-
"""Prueba en vivo: corrige un profesor en Supabase, verifica los archivos y
deshace. Se borra al terminar."""
import json
import re
import subprocess
import sys
from pathlib import Path

import requests

BASE = Path(__file__).parent
cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))["supabase"]
url, key = cfg["url"].rstrip("/"), cfg["anon_key"]
tabla = cfg.get("tabla", "ediciones")
API = f"{url}/rest/v1/{tabla}"
CAB = {"apikey": key, "Authorization": f"Bearer {key}",
       "Content-Type": "application/json", "Accept": "application/json",
       "Prefer": "return=representation"}


def correr(*args):
    r = subprocess.run([sys.executable, "main.py", *args], cwd=BASE,
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace")
    texto = (r.stdout or "") + (r.stderr or "")
    return r.returncode, texto


def principal(archivo: str) -> str:
    return (BASE / "salida" / archivo).read_text(encoding="utf-8")


def main() -> int:
    # ---- 1. elige un evento real de la página y su clave de identidad ----
    pagina = principal("calendario_evaluaciones.html")
    datos = json.loads(
        re.search(r'id="datos">([\s\S]*?)</script>', pagina).group(1)
        .replace("<\\/", "</"))
    ev = next(e for e in datos["eventos"] if e["f"] == "2026-10-14")
    clave, profesor, fecha = ev["k"], ev["p"], ev["f"]
    print(f"objetivo: {ev['a']} {ev['e']} ({fecha}) · clave {clave}")
    print(f"          profesor actual: «{profesor}»")

    # ---- 2. inserta la corrección (lo que haría la página) ----
    nuevo = "PROF. CORREGIDO POR LA NUBE"
    alta = requests.post(API, headers=CAB, timeout=30, json={
        "tipo": "correccion", "clave": clave,
        "campos": {"PROFESOR": nuevo}, "previo": {"PROFESOR": profesor},
        "autor": "prueba en vivo", "token": "e2e"})
    print("POST corrección ->", alta.status_code)
    if alta.status_code not in (200, 201):
        print(alta.text[:400])
        return 1
    fila = alta.json()[0]

    # ---- 3. la corrida de las 07:00 debe reflejarlo en los archivos ----
    codigo, texto = correr("--formatos", "html,json")
    assert codigo == 0, texto
    linea = [l for l in texto.splitlines() if "Correcciones aplicadas" in l]
    print("  ", linea[0] if linea else "(sin línea de correcciones)")
    assert "1 corregidas" in texto, texto
    json_salida = json.loads(
        (BASE / "salida" / "calendario_evaluaciones.json")
        .read_text("utf-8"))["registros"]
    objetivo = [r for r in json_salida if r["FECHA"] == fecha
                and r["ASIGNATURA"] == ev["a"] and r["NUMERO"] == ev["n"]]
    assert objetivo and objetivo[0]["PROFESOR"] == nuevo, objetivo
    assert nuevo in principal("calendario_evaluaciones.html")
    print("  ok  la corrección aparece en el JSON y en la página")

    # ---- 4. deshacer (registro «anula») y comprobar que vuelve ----
    anula = requests.post(API, headers=CAB, timeout=30, json={
        "tipo": "anula", "clave": clave, "anula": fila["id"],
        "campos": {}, "previo": {}, "autor": "prueba en vivo", "token": "e2e"})
    print("POST anula     ->", anula.status_code)
    if anula.status_code not in (200, 201):
        print(anula.text[:400])
        return 1

    codigo, texto = correr("--formatos", "html,json")
    assert codigo == 0, texto
    json_salida = json.loads(
        (BASE / "salida" / "calendario_evaluaciones.json")
        .read_text("utf-8"))["registros"]
    objetivo = [r for r in json_salida if r["FECHA"] == fecha
                and r["ASIGNATURA"] == ev["a"] and r["NUMERO"] == ev["n"]]
    assert objetivo[0]["PROFESOR"] == profesor, objetivo[0]
    assert nuevo not in principal("calendario_evaluaciones.html")
    print("  ok  tras «anula» el dato vuelve al original")

    # ---- 5. ninguna de LAS FILAS DE ESTA PRUEBA queda activa ----
    filas = requests.get(API, params={"select": "*"}, headers=CAB, timeout=30).json()
    nuestras = {f["id"] for f in filas
                if f.get("autor") == "prueba en vivo"
                and f.get("tipo") in ("correccion", "nuevo")}
    anuladas = {f.get("anula") for f in filas if f.get("anula")}
    activas = [f for f in filas if f["id"] in nuestras and f["id"] not in anuladas]
    print(f"  filas en la nube: {len(filas)} · de esta prueba activas: {len(activas)}")
    assert not activas, activas
    print("\nE2E OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
