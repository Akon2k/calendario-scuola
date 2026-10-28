const ENDPOINT = 'https://translation.googleapis.com/language/translate/v2';

function decodificar(valor) {
  const entidades = {
    amp: '&', lt: '<', gt: '>', quot: '"', apos: "'", nbsp: ' ',
    aacute: 'á', eacute: 'é', iacute: 'í', oacute: 'ó', uacute: 'ú',
    Aacute: 'Á', Eacute: 'É', Iacute: 'Í', Oacute: 'Ó', Uacute: 'Ú',
    ntilde: 'ñ', Ntilde: 'Ñ', uuml: 'ü', Uuml: 'Ü'
  };
  return valor.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);/gi, (original, codigo) => {
    if (codigo[0] !== '#') return entidades[codigo] ?? entidades[codigo.toLowerCase()] ?? original;
    const n = codigo[1].toLowerCase() === 'x' ? parseInt(codigo.slice(2), 16) : Number(codigo.slice(1));
    return Number.isInteger(n) && n > 0 && n <= 0x10ffff && !(n >= 0xd800 && n <= 0xdfff)
      ? String.fromCodePoint(n) : original;
  });
}

export async function hashTitulo(titulo) {
  const bytes = await crypto.subtle.digest('SHA-256', new TextEncoder().encode('google-nmt:it:es:' + titulo));
  return Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, '0')).join('');
}

export async function traducirGoogle(titulo, key, fetcher = fetch) {
  if (!key || typeof titulo !== 'string' || !titulo.trim() || Array.from(titulo).length > 1000) return null;
  try {
    const r = await fetcher(ENDPOINT, {
      method: 'POST', redirect: 'error', signal: AbortSignal.timeout(12000),
      headers: {'x-goog-api-key': key, 'Content-Type': 'application/json; charset=utf-8'},
      body: JSON.stringify({q: [titulo], source: 'it', target: 'es', format: 'text', model: 'nmt'}),
    });
    // Nunca devolver ni registrar errores de Google: podrían contener datos
    // de la cuenta. No hay reintento inmediato que duplique el consumo.
    if (!r.ok) return null;
    const j = await r.json();
    if (!Array.isArray(j?.data?.translations) || j.data.translations.length !== 1) return null;
    const texto = j.data.translations[0].translatedText;
    if (typeof texto !== 'string' || texto.length > 10000) return null;
    const resultado = decodificar(texto).trim();
    return resultado && Array.from(resultado).length <= 1500 ? resultado : null;
  } catch { return null; }
}

export async function traducirPendiente(titulo, deps) {
  if (!deps.key || typeof titulo !== 'string' || !titulo.trim() || Array.from(titulo).length > 1000) return null;
  const hash = await hashTitulo(titulo);
  let trabajo;
  try {
    // La BD contabiliza y reserva caracteres ANTES de llamar al proveedor.
    // Las visitas del lector nunca invocan esta operación.
    trabajo = await deps.reservar(hash, titulo);
    if (trabajo?.estado === 'cache') return trabajo.traduccion;
    if (trabajo?.estado !== 'reservada' || !trabajo.lease) return null;
    const texto = await traducirGoogle(titulo, deps.key, deps.fetcher || fetch);
    const guardado = await deps.guardar(hash, trabajo.lease, texto);
    return guardado ? texto : null;
  } catch {
    if (trabajo?.lease) await deps.guardar(hash, trabajo.lease, null).catch(() => {});
    return null;
  }
}
