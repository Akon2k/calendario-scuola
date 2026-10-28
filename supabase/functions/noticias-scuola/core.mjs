export const HOST = 'scuola.scuolaitalianadiconcepcion.cl';
export const AGENTE = 'Mozilla/5.0 (compatible; ScuolaCalendario/1.0)';

export function validarUrl(valor) {
  try {
    const u = new URL(valor);
    if (u.protocol !== 'https:' || u.hostname !== HOST || u.username || u.password || u.port || u.search || u.hash) return false;
    const m = u.pathname.match(/^\/2026\/(\d{2})\/(\d{2})\/[a-z0-9-]+\/$/);
    if (!m) return false;
    const f = new Date(`2026-${m[1]}-${m[2]}T00:00:00Z`);
    return Number.isFinite(f.getTime()) && f.toISOString().slice(0, 10) === `2026-${m[1]}-${m[2]}`;
  } catch { return false; }
}

export async function descargar(url, fetcher = fetch) {
  const respuesta = await fetcher(url, {
    headers: {'User-Agent': AGENTE}, redirect: 'error', signal: AbortSignal.timeout(18000),
  });
  if (!respuesta.ok || !respuesta.body) throw new Error('Fuente no disponible');
  const lector = respuesta.body.getReader();
  const partes = []; let total = 0;
  try {
    while (true) {
      const {done, value} = await lector.read(); if (done) break;
      total += value.length;
      if (total > 2_000_000) throw new Error('Fuente demasiado grande');
      partes.push(value);
    }
  } finally { await lector.cancel().catch(() => {}); }
  const unido = new Uint8Array(total); let offset = 0;
  for (const p of partes) { unido.set(p, offset); offset += p.length; }
  return new TextDecoder().decode(unido);
}

export function extraerTexto(html, parseHTML) {
  const {document} = parseHTML(html);
  const raiz = document.querySelector('article .entry-content');
  if (!raiz) throw new Error('No se reconoce el contenido');
  raiz.querySelectorAll('script,style,nav,header,footer,aside,form,figure,img,video,audio,iframe,button,svg,.entry-footer,.sharedaddy,.post-navigation,.comments-area')
    .forEach(n => n.remove());
  const parrafos = [];
  for (const nodo of raiz.querySelectorAll('p,h1,h2,h3,h4,h5,h6,li,blockquote,td')) {
    if (nodo.querySelector('p,li,blockquote,td')) continue;
    const t = nodo.textContent.replace(/\s+/g, ' ').trim();
    if (t) parrafos.push(t);
  }
  const texto = parrafos.join('\n\n');
  if (texto.length < 40 || texto.length > 100000) throw new Error('No hay un texto completo utilizable');
  return texto;
}

function origenPermitido(origen) {
  if (!origen) return true; // cron y clientes sin navegador; los datos son públicos.
  if (origen === 'https://akon2k.github.io') return true;
  try {
    const u = new URL(origen);
    return u.protocol === 'http:' && ['127.0.0.1', 'localhost', '[::1]'].includes(u.hostname) && u.port === '8765';
  } catch { return false; }
}

export function crearHandler(deps) {
  return async function (req) {
    const origen = req.headers.get('origin');
    const headers = {'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store', 'Vary': 'Origin'};
    if (origen && origenPermitido(origen)) headers['Access-Control-Allow-Origin'] = origen;
    const respuesta = (obj, status = 200, extra = {}) => new Response(JSON.stringify(obj), {status, headers: {...headers, ...extra}});
    if (!origenPermitido(origen)) return respuesta({error: 'Origen no permitido'}, 403);
    if (req.method === 'OPTIONS') return respuesta({}, 200, {
      'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
      'Access-Control-Allow-Headers': 'apikey, authorization, content-type, x-noticias-secret',
    });
    if (req.method === 'POST') {
      if (!deps.secreto || req.headers.get('x-noticias-secret') !== deps.secreto) return respuesta({error: 'No autorizado'}, 401);
      try { return respuesta(await deps.sincronizar()); }
      catch { return respuesta({error: 'No se pudieron actualizar las noticias'}, 503); }
    }
    if (req.method !== 'GET') return respuesta({error: 'Método no permitido'}, 405);
    const query = new URL(req.url).searchParams;
    const id = query.get('id');
    if (Array.from(query.keys()).some(k => k !== 'id') || !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id || '')) {
      return respuesta({error: 'Identificador no válido'}, 400);
    }
    let lease;
    try {
      const noticia = await deps.leer(id);
      if (!noticia) return respuesta({error: 'Noticia no encontrada'}, 404);
      if (!validarUrl(noticia.url)) return respuesta({error: 'Fuente no permitida'}, 400);
      const datos = texto => ({id: noticia.id, titulo: noticia.titulo, titulo_es: noticia.titulo_es,
        fecha: noticia.fecha, url: noticia.url, texto});
      if (noticia.texto) return respuesta(datos(noticia.texto), 200, {'Cache-Control': 'public, max-age=3600'});
      lease = await deps.reservar(id);
      if (!lease) return respuesta({error: 'La noticia se está preparando; inténtalo en un momento'}, 202, {'Retry-After': '3'});
      const texto = await deps.extraer(noticia.url);
      const guardado = await deps.guardar(id, lease, texto);
      if (!guardado) throw new Error('La reserva caducó');
      return respuesta(datos(texto), 200, {'Cache-Control': 'public, max-age=3600'});
    } catch {
      if (lease) await deps.guardar(id, lease, null).catch(() => {});
      return respuesta({error: 'No pude obtener el texto. Puedes abrir la publicación original.'}, 503);
    }
  };
}
