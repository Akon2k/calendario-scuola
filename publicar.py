# -*- coding: utf-8 -*-
"""Sube `salida/` a GitHub Pages: la URL fija de la PWA.

La página (HTML + manifest + sw.js + iconos) queda publicada en
`https://<usuario>.github.io/<repo>/` y se actualiza sola en cada corrida
de la tarea programada. El código fuente NO se sube: sólo los archivos que
genera `main.py` en `salida/`.

Uso:
    python publicar.py            # sube sólo lo que cambió
    python publicar.py --forzar   # sube todo aunque no haya cambios

Requiere GitHub CLI autenticado (`gh auth login`): de ahí sale el token
(esta máquina ya está logueada). La configuración es el bloque «github»
de config.json:

    "github": { "repo": "calendario-scuola" }

Primera corrida: crea el repo público, sube los archivos, habilita Pages
y espera a que compile. Si GitHub falla, deja el error en el log y devuelve
código distinto de cero sin romper lo demás.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

# Consolas cp1252 de Windows: que un símbolo raro no corte la corrida.
for _salida in (sys.stdout, sys.stderr):
    try:
        _salida.reconfigure(errors="replace")
    except (AttributeError, ValueError):
        pass

RAIZ = Path(__file__).resolve().parent
CONFIG = RAIZ / "config.json"
SALIDA = RAIZ / "salida"
LOGS = RAIZ / "logs"
API = "https://api.github.com"
REPO_POR_DEFECTO = "calendario-scuola"

# nombre local -> nombre en el repo (index.html es lo que Pages sirve como /)
ARCHIVOS = [
    ("calendario_evaluaciones.html", "index.html"),
    ("manifest.webmanifest", "manifest.webmanifest"),
    ("sw.js", "sw.js"),
    ("icon-192.png", "icon-192.png"),
    ("icon-512.png", "icon-512.png"),
    ("icon-maskable-512.png", "icon-maskable-512.png"),
    ("apple-touch-icon.png", "apple-touch-icon.png"),
]


def registrar(mensaje: str) -> None:
    sello = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    linea = f"[{sello}] {mensaje}"
    print(linea)
    try:
        LOGS.mkdir(exist_ok=True)
        with (LOGS / "publicar.log").open("a", encoding="utf-8") as archivo:
            archivo.write(linea + "\n")
    except OSError:
        pass


def _gh(*argumentos: str) -> str:
    """Ejecuta `gh` y devuelve la salida (stderr limpio si falla)."""
    try:
        proceso = subprocess.run(["gh", *argumentos], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace")
    except FileNotFoundError:
        raise RuntimeError("No está el GitHub CLI (gh). Instálalo con: winget install GitHub.cli")
    if proceso.returncode != 0:
        detalle = (proceso.stderr or proceso.stdout or "").strip().splitlines()
        raise RuntimeError("gh " + argumentos[0] + ": " + (detalle[-1] if detalle else "error"))
    return proceso.stdout.strip()


def _sesion() -> tuple[requests.Session, str]:
    token = _gh("auth", "token")
    if not token:
        raise RuntimeError("gh no está autenticado. Ejecuta: gh auth login")
    sesion = requests.Session()
    sesion.headers.update({
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    usuario = sesion.get(f"{API}/user", timeout=20).json()["login"]
    return sesion, usuario


def _huella(ruta: Path) -> str:
    return hashlib.sha256(ruta.read_bytes()).hexdigest()


def publicar(repo: str, forzar: bool) -> str:
    """Sube los archivos cambiados y devuelve la URL pública."""
    faltan = [origen for origen, _ in ARCHIVOS if not (SALIDA / origen).exists()]
    if "calendario_evaluaciones.html" in faltan:
        raise RuntimeError("No está salida/calendario_evaluaciones.html: corre `python main.py` primero")
    if faltan:
        registrar("Faltan archivos (se publica sin ellos): " + ", ".join(faltan))

    estado_ruta = LOGS / "publicado.json"
    try:
        estado = json.loads(estado_ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        estado = {}

    plan = [(o, d) for o, d in ARCHIVOS
            if not (SALIDA / o).exists() or forzar
            or _huella(SALIDA / o) != estado.get(d)]
    if not plan:
        registrar("Página al día: nada que subir")
        usuario_previo = str(estado.get("__usuario__") or "")
        return f"https://{usuario_previo}.github.io/{repo}/" if usuario_previo else ""

    sesion, usuario = _sesion()
    registro_repo = sesion.get(f"{API}/repos/{usuario}/{repo}", timeout=20)
    if registro_repo.status_code == 404:
        registrar(f"Creando el repositorio público «{usuario}/{repo}»…")
        creado = sesion.post(f"{API}/user/repos", timeout=30, json={
            "name": repo,
            "description": "Calendario de Evaluaciones de la Scuola Italiana (PWA)",
            "private": False,
            "has_issues": False,
            "has_projects": False,
            "has_wiki": False,
        })
        if creado.status_code not in (200, 201):
            raise RuntimeError(f"no se pudo crear el repo: HTTP {creado.status_code} "
                               f"{creado.text[:160]}")
        rama = creado.json().get("default_branch") or "main"
    elif registro_repo.status_code != 200:
        raise RuntimeError(f"GET /repos/{usuario}/{repo}: HTTP {registro_repo.status_code}")
    else:
        rama = registro_repo.json().get("default_branch") or "main"

    sello = datetime.now().strftime("%Y-%m-%d %H:%M")
    for origen, destino in plan:
        ruta = SALIDA / origen
        if not ruta.exists():
            continue
        contenido = base64.b64encode(ruta.read_bytes()).decode("ascii")
        actual = sesion.get(f"{API}/repos/{usuario}/{repo}/contents/{destino}",
                            params={"ref": rama}, timeout=20)
        if actual.status_code not in (200, 404):
            raise RuntimeError(f"GET contents/{destino}: HTTP {actual.status_code}")
        cuerpo = {"message": f"publicar {sello}", "content": contenido, "branch": rama}
        if actual.status_code == 200:
            cuerpo["sha"] = actual.json()["sha"]
        subido = sesion.put(f"{API}/repos/{usuario}/{repo}/contents/{destino}",
                            json=cuerpo, timeout=60)
        if subido.status_code not in (200, 201):
            raise RuntimeError(f"PUT contents/{destino}: HTTP {subido.status_code} "
                               f"{subido.text[:160]}")
        registrar(f"subido {destino} ({len(ruta.read_bytes()):,} bytes)")

    # .nojekyll: sin él, Pages pasa los archivos por Jekyll y puede ignorarlos
    if ".nojekyll" not in estado:
        actual = sesion.get(f"{API}/repos/{usuario}/{repo}/contents/.nojekyll",
                            params={"ref": rama}, timeout=20)
        if actual.status_code == 404:
            cuerpo = {"message": f"publicar {sello}",
                      "content": "", "branch": rama}
            r = sesion.put(f"{API}/repos/{usuario}/{repo}/contents/.nojekyll",
                           json=cuerpo, timeout=30)
            if r.status_code in (200, 201):
                registrar("subido .nojekyll")
        estado[".nojekyll"] = "hecho"

    # Activar Pages si aún no lo está (409 = ya activo)
    paginas = sesion.get(f"{API}/repos/{usuario}/{repo}/pages", timeout=20)
    if paginas.status_code == 404:
        activar = sesion.post(f"{API}/repos/{usuario}/{repo}/pages", timeout=30,
                              json={"source": {"branch": rama, "path": "/"}})
        if activar.status_code in (200, 201):
            registrar("GitHub Pages activado")
        elif activar.status_code != 409:
            registrar(f"aviso: no se pudo activar Pages (HTTP {activar.status_code}); "
                      "actívalo a mano en Settings → Pages")

    # Esperar a que compile la primera versión (lo mejor de 90 s)
    url = f"https://{usuario}.github.io/{repo}/"
    for _ in range(45):
        construccion = sesion.get(f"{API}/repos/{usuario}/{repo}/pages/builds/latest",
                                  timeout=20)
        if construccion.status_code == 200:
            estado_build = construccion.json().get("status")
            if estado_build == "built":
                break
            if estado_build in ("errored", "failure"):
                registrar("aviso: la compilación de Pages reportó error")
                break
        time.sleep(2)
    else:
        registrar("aviso: Pages sigue compilando; la URL se habilita en unos minutos")

    # Guardar huellas sólo si todo salió bien (si no, se reintenta al próximo)
    nuevo_estado = {destino: _huella(SALIDA / origen)
                    for origen, destino in ARCHIVOS if (SALIDA / origen).exists()}
    nuevo_estado["__usuario__"] = usuario
    nuevo_estado.update({k: v for k, v in estado.items() if k == ".nojekyll"})
    estado_ruta.write_text(json.dumps(nuevo_estado, indent=2), encoding="utf-8")
    return url


def principal(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Publica la página en GitHub Pages.")
    parser.add_argument("--forzar", action="store_true",
                        help="sube todos los archivos aunque no hayan cambiado")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args(argv)

    try:
        config = json.loads(args.config.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        registrar(f"No se pudo leer {args.config.name}: {exc}")
        return 1
    repo = str((config.get("github") or {}).get("repo") or REPO_POR_DEFECTO)

    try:
        url = publicar(repo, args.forzar)
    except RuntimeError as exc:
        registrar(f"ERROR AL PUBLICAR: {exc}")
        return 1
    except requests.RequestException as exc:
        registrar(f"ERROR DE RED AL PUBLICAR: {exc}")
        return 1
    if url:
        registrar(f"Publicado en {url}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(principal())
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)
