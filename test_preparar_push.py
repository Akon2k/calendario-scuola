"""Prueba local: sólo usa credenciales ficticias en una carpeta temporal."""
import json
import tempfile
from pathlib import Path

from preparar_push import preparar


def main():
    with tempfile.TemporaryDirectory() as carpeta:
        raiz = Path(carpeta)
        config = {"rut": "NO-COPIAR", "password": "NO-COPIAR",
                  "supabase": {"url": "https://proyectoprueba.supabase.co", "anon_key": "NO-COPIAR"},
                  "avisos": {"vapid_publica": "A" * 87, "vapid_privada": "B" * 43,
                             "sujetos": "mailto:prueba@example.com"}}
        (raiz / "config.json").write_text(json.dumps(config), encoding="utf-8")
        destino = preparar(raiz)
        env = (destino / "servidor.env").read_text(encoding="utf-8")
        valores = {k: json.loads(v) for k, v in
                   (linea.split("=", 1) for linea in env.splitlines())}
        sql = (destino / "configurar_webhook.sql").read_text(encoding="utf-8")
        assert valores["PUSH_WEBHOOK_SECRET"] in sql
        assert len(valores["PUSH_WEBHOOK_SECRET"]) >= 48
        assert "activo = true" not in sql
        assert "NO-COPIAR" not in env + sql
        assert valores["VAPID_PRIVATE_KEY"] == "B" * 43
        assert "service_role" not in env
        try:
            preparar(raiz)
        except FileExistsError:
            pass
        else:
            raise AssertionError("No debe rotar secretos al ejecutar otra vez")
        assert env == (destino / "servidor.env").read_text(encoding="utf-8")
    print("TODO OK: secretos sólo locales, sin credenciales de EduFácil, no activa ni sobrescribe")


if __name__ == "__main__":
    main()
