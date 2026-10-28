# -*- coding: utf-8 -*-
"""Prepara importación pública y configuración privada. Nunca imprime claves.

No ejecuta SQL ni publica la web. Los archivos privados van a logs/ (ignorado).
"""
import json
import secrets
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def literal(valor):
    return "'" + str(valor).replace("'", "''") + "'"


def main():
    destino = RAIZ / 'logs' / 'noticias-scuola'
    destino.mkdir(parents=True, exist_ok=True)
    datos = json.loads((RAIZ / 'salida/noticias_scuola.json').read_text(encoding='utf-8'))
    traducciones = json.loads((RAIZ / 'supabase/functions/noticias-scuola/traducciones.json').read_text(encoding='utf-8'))
    filas = []
    for n in datos['noticias']:
        filas.append({'url': n['url'], 'fecha': n['fecha'], 'titulo': n['titulo'],
                      'titulo_es': traducciones.get(n['titulo']) or n.get('titulo_es'), 'detalle': n.get('detalle', ''),
                      'miniatura': n.get('miniatura', '')})
    sql = ('begin; insert into public.noticias_scuola(url,fecha,titulo,titulo_es,detalle,miniatura) '
           'select url,fecha,titulo,titulo_es,detalle,miniatura from jsonb_to_recordset('
           + literal(json.dumps(filas, ensure_ascii=False))
           + '::jsonb) as x(url text, fecha date, titulo text, titulo_es text, detalle text, miniatura text) '
           'on conflict(url) do update set titulo=excluded.titulo,titulo_es=excluded.titulo_es,'
           'detalle=excluded.detalle,miniatura=excluded.miniatura; commit; '
           'select count(*) as noticias, count(titulo_es) as traducidas from public.noticias_scuola;')
    (destino / 'importar.sql').write_text(sql, encoding='utf-8')
    env = destino / 'servidor.env'
    if not env.exists():
        env.write_text('NOTICIAS_ADMIN_SECRET=' + secrets.token_urlsafe(48) + '\n', encoding='utf-8')
    secreto = env.read_text(encoding='utf-8').strip().split('=', 1)[1]
    url = 'https://icblrmookmpmzpnjeeeh.supabase.co/functions/v1/noticias-scuola'
    configurar = """begin;
do $bloque$ declare existente uuid; begin
 select id into existente from vault.secrets where name = 'noticias_scuola_secret';
 if existente is null then
   perform vault.create_secret(SECRETO, 'noticias_scuola_secret');
 else
   perform vault.update_secret(existente, SECRETO);
 end if;
end $bloque$;
create or replace function public.noticias_scuola_despertar()
returns void language plpgsql security definer set search_path = '' as $$
declare secreto text;
begin
 select decrypted_secret into secreto from vault.decrypted_secrets where name = 'noticias_scuola_secret' limit 1;
 if secreto is null then return; end if;
 perform net.http_post(url := URL_FUNCION, body := '{}'::jsonb,
   headers := jsonb_build_object('Content-Type','application/json','x-noticias-secret',secreto), timeout_milliseconds := 60000);
end;
$$;
revoke all on function public.noticias_scuola_despertar() from public, anon, authenticated;
grant execute on function public.noticias_scuola_despertar() to service_role;
do $bloque$ begin
 if not exists(select 1 from cron.job where jobname='noticias-scuola-15min') then
  perform cron.schedule('noticias-scuola-15min','*/15 * * * *','select public.noticias_scuola_despertar();');
 end if;
end $bloque$;
commit;
""".replace('SECRETO', literal(secreto)).replace('URL_FUNCION', literal(url))
    (destino / 'configurar.sql').write_text(configurar, encoding='utf-8')
    print(f'Preparación local: {len(filas)} noticias, {sum(bool(n["titulo_es"]) for n in filas)} títulos traducidos.')
    print('SQL y secreto preparados en logs/noticias-scuola/. No se publican ni se imprimen claves.')


if __name__ == '__main__':
    main()
