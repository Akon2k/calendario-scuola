import {createClient} from 'npm:@supabase/supabase-js@2.106.1';
import {parseHTML} from 'npm:linkedom@0.18.12';
import traducciones from './traducciones.json' with {type: 'json'};
import {crearHandler, descargar, extraerTexto, validarUrl, HOST} from './core.mjs';
import {traducirPendiente} from './google.mjs';

const sb = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!,
  {auth: {persistSession: false}});
const mapa = traducciones as Record<string, string>;
function plano(html: string): string {
  const {document} = parseHTML('<html><body>' + html + '</body></html>');
  document.querySelectorAll('script,style,iframe').forEach(n => n.remove());
  return document.body.textContent.replace(/\s+/g, ' ').trim();
}
async function rpc(nombre: string, parametros: Record<string, unknown>) {
  const {data, error} = await sb.rpc(nombre, parametros);
  if (error) throw new Error('Operación de caché no disponible');
  return data;
}

// Sólo títulos pendientes; las lecturas públicas nunca llaman a Google.
// La clave y el interruptor privado deben configurarse antes de gastar.
async function traducir(titulo: string): Promise<string | null> {
  if (mapa[titulo]) return mapa[titulo];
  return traducirPendiente(titulo, {
    key: Deno.env.get('GOOGLE_TRANSLATE_API_KEY'),
    reservar: (hash: string, original: string) => rpc('noticias_traduccion_reservar', {p_hash: hash, p_titulo: original}),
    guardar: (hash: string, lease: string, texto: string | null) => rpc('noticias_traduccion_guardar',
      {p_hash: hash, p_lease: lease, p_traduccion: texto}),
  });
}

async function sincronizar() {
  const {data: guardadas, error: fallo} = await sb.from('noticias_scuola').select('url,titulo,titulo_es,titulo_es_proveedor,fecha,detalle,miniatura,fuente_modificada');
  if (fallo) throw new Error('Caché no disponible');
  const anteriores = new Map((guardadas || []).map(n => [n.url, n]));
  const hoy = new Intl.DateTimeFormat('en-CA', {timeZone: 'America/Santiago', year: 'numeric', month: '2-digit', day: '2-digit'}).format(new Date());
  let total = 0, nuevas = 0, intentosTraduccion = 0;
  for (let pagina = 1; pagina <= 3; pagina++) {
    const u = new URL('https://' + HOST + '/wp-json/wp/v2/posts');
    u.search = new URLSearchParams({categories: '32', after: '2026-01-01T00:00:00', before: '2027-01-01T00:00:00',
      per_page: '100', page: String(pagina), _embed: 'wp:featuredmedia', _fields: 'link,date,modified,title,excerpt,_links,_embedded'}).toString();
    const entradas = JSON.parse(await descargar(u.href));
    if (!Array.isArray(entradas)) throw new Error('Formato de fuente no válido');
    const filas = [];
    for (const e of entradas) {
      if (!validarUrl(e.link)) continue;
      const fecha = e.date?.slice(0, 10);
      if (!/^2026-\d{2}-\d{2}$/.test(fecha || '') || fecha > hoy) continue;
      const titulo = plano(e.title?.rendered || '');
      if (!titulo || titulo.length > 1000) continue;
      const anterior = anteriores.get(e.link);
      let titulo_es = anterior?.titulo === titulo ? anterior.titulo_es : null;
      let titulo_es_proveedor = titulo_es ? anterior?.titulo_es_proveedor || 'manual' : 'manual';
      if (!titulo_es && mapa[titulo]) { titulo_es = mapa[titulo]; titulo_es_proveedor = 'manual'; }
      if (!titulo_es && intentosTraduccion < 5 && Deno.env.get('GOOGLE_TRANSLATE_API_KEY')) {
        intentosTraduccion++; titulo_es = await traducir(titulo);
        if (titulo_es) titulo_es_proveedor = 'google';
      }
      const candidatas: {puntaje: number; url: string}[] = [];
      for (const m of e._embedded?.['wp:featuredmedia'] || []) {
        for (const s of Object.values(m.media_details?.sizes || {}) as any[]) {
          try {
            const i = new URL(s.source_url);
            if (i.protocol === 'https:' && i.hostname === HOST && !i.port && !i.username && !i.password
                && i.pathname.startsWith('/wp-content/uploads/') && s.width > 0 && s.height > 0 && s.width <= 300 && s.height <= 300) {
              candidatas.push({puntaje: Math.abs(s.width - 150) + Math.abs(s.height - 150), url: i.href});
            }
          } catch { /* sin miniatura antes que descargar una imagen grande */ }
        }
      }
      candidatas.sort((a, b) => a.puntaje - b.puntaje);
      const fila = {url: e.link, titulo, titulo_es, titulo_es_proveedor, fecha, detalle: plano(e.excerpt?.rendered || '').slice(0, 10000),
        miniatura: candidatas[0]?.url || '', fuente_modificada: e.modified || null, consultado: new Date().toISOString()};
      total++;
      if (!anterior || ['titulo','titulo_es','titulo_es_proveedor','fecha','detalle','miniatura','fuente_modificada'].some(k =>
        (fila as any)[k] !== (anterior as any)[k])) filas.push(fila);
      if (!anterior) nuevas++;
    }
    if (filas.length) {
      const {error} = await sb.from('noticias_scuola').upsert(filas, {onConflict: 'url'});
      if (error) throw new Error('No se pudieron guardar las novedades');
    }
    if (entradas.length < 100) break;
  }
  return {ok: true, revisadas: total, nuevas};
}

Deno.serve(crearHandler({
  secreto: Deno.env.get('NOTICIAS_ADMIN_SECRET'), sincronizar,
  leer: async (id: string) => {
    const {data, error} = await sb.from('noticias_scuola').select('id,url,titulo,titulo_es,fecha,texto').eq('id', id).maybeSingle();
    if (error) throw new Error('Lectura no disponible');
    return data;
  },
  reservar: (id: string) => rpc('noticias_scuola_reservar', {p_id: id}),
  guardar: (id: string, lease: string, texto: string | null) => rpc('noticias_scuola_guardar', {p_id: id, p_lease: lease, p_texto: texto}),
  extraer: async (url: string) => {
    if (!validarUrl(url)) throw new Error('Fuente no permitida');
    return extraerTexto(await descargar(url), parseHTML);
  },
}));
