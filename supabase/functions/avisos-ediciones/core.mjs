// Lógica sin red ni secretos: se prueba con node --test test_push_inmediato.mjs.
const CAMPOS = {
  FECHA: 'fecha', ASIGNATURA: 'asignatura', ABREVIATURA: 'código',
  EVALUACION: 'evaluación', CONTENIDO: 'contenido', PROFESOR: 'profesor',
  NUMERO: 'número', COEFICIENTE: 'coeficiente', PONDERACION: 'ponderación',
  TIPO: 'tipo',
};

function texto(valor, max = 100) {
  return String(valor ?? '').replace(/[\u0000-\u001f\u007f]/g, ' ')
    .replace(/\s+/g, ' ').trim().slice(0, max);
}

function fecha(valor) {
  const s = texto(valor, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) ? s.split('-').reverse().join('/') : s;
}

export function crearMensaje(fila, pagina) {
  const campos = fila.campos || {}, previo = fila.previo || {};
  const partes = String(fila.clave || '').split('#')[0].split('|');
  const nombre = texto(campos.ASIGNATURA || partes[0]) || 'Actividad';
  const numero = texto(campos.NUMERO || partes[1], 20);
  const identidad = nombre + (numero ? ' · n° ' + numero : '');
  const autor = texto(fila.autor, 60);
  const firma = autor ? ' · ' + autor : '';
  let titulo, cuerpo;
  switch (fila.tipo) {
    case 'nuevo':
      titulo = '➕ Nueva actividad';
      cuerpo = identidad + (campos.FECHA ? ' · ' + fecha(campos.FECHA) : '')
        + (campos.EVALUACION ? ': ' + texto(campos.EVALUACION, 110) : '') + firma;
      break;
    case 'adjunto':
      titulo = '📎 Nuevo material PDF';
      cuerpo = identidad + ': ' + texto(campos.nombre || 'material.pdf', 120) + firma;
      break;
    case 'anula':
      titulo = '↩️ Cambio deshecho';
      cuerpo = identidad + ': se quitó un material o se deshizo una edición' + firma;
      break;
    case 'correccion': {
      const cambios = Object.keys(campos).filter((k) => CAMPOS[k]
        && String(campos[k] ?? '') !== String(previo[k] ?? ''));
      if (!cambios.length) return null;
      titulo = cambios.includes('FECHA') ? '📅 Cambio de fecha' : '✏️ Actividad actualizada';
      const detalle = cambios.map((k) => {
        if (k !== 'FECHA') return CAMPOS[k];
        return 'fecha: ' + (previo.FECHA ? fecha(previo.FECHA) + ' → ' : '')
          + fecha(campos.FECHA);
      }).join(', ');
      cuerpo = identidad + ' · ' + detalle + firma;
      break;
    }
    default: return null;
  }
  return { titulo, cuerpo: texto(cuerpo, 300), url: pagina,
    // El mismo reintento reemplaza el aviso anterior en vez de apilarlo.
    tag: 'edicion-' + fila.id };
}

// Las suscripciones son públicas: no permitir que se usen para acceder a
// direcciones internas o mandar peticiones arbitrarias desde el servidor.
export function endpointPermitido(endpoint) {
  try {
    const u = new URL(endpoint);
    if (u.protocol !== 'https:' || u.username || u.password
        || (u.port && u.port !== '443')) return false;
    return ['fcm.googleapis.com', 'android.googleapis.com', 'web.push.apple.com',
      'updates.push.services.mozilla.com'].includes(u.hostname)
      || u.hostname.endsWith('.notify.windows.com');
  } catch { return false; }
}

export async function procesarTrabajo(trabajo, { enviar, resultado, pagina }) {
  const mensaje = crearMensaje(trabajo.edicion, pagina);
  const totales = { enviados: 0, caducas: 0, errores: 0, omitidos: 0 };
  // Como máximo cinco envíos simultáneos; cada envío tiene su timeout.
  const entregas = trabajo.entregas || [];
  for (let i = 0; i < entregas.length; i += 5) {
    await Promise.all(entregas.slice(i, i + 5).map(async (suscripcion) => {
      let estado = 'enviado';
      if (!mensaje) estado = 'omitido';
      else if (!endpointPermitido(suscripcion.endpoint)) estado = 'caduca';
      else {
        try { await enviar(suscripcion, mensaje); }
        catch (err) {
          estado = [404, 410].includes(Number(err?.statusCode)) ? 'caduca' : 'error';
        }
      }
      // Si falla guardar el resultado, NO dar la entrega por finalizada:
      // el lease vence y la cola la vuelve a intentar con el mismo tag.
      await resultado(trabajo.id, trabajo.lease, suscripcion.endpoint, estado);
      const contador = { enviado: 'enviados', caduca: 'caducas', error: 'errores', omitido: 'omitidos' };
      totales[contador[estado]]++;
    }));
  }
  return totales;
}

export function crearHandler({ secreto, tomar, procesar, soltar, despertar }) {
  return async function (req) {
    if (req.method !== 'POST') return new Response('Sólo POST', { status: 405 });
    // No se acepta la anon key, ni se confía en filas enviadas por el navegador.
    if (!secreto || req.headers.get('x-webhook-secret') !== secreto) {
      return new Response('No autorizado', { status: 401 });
    }
    try {
      const trabajo = await tomar();
      if (!trabajo) return Response.json({ pendientes: false });
      const resumen = await procesar(trabajo);
      await soltar(trabajo.id, trabajo.lease);
      await despertar();
      return Response.json(resumen);
    } catch {
      // No imprimir excepciones de web-push: pueden contener endpoints y claves.
      return Response.json({ error: 'El envío queda pendiente para reintentar' }, { status: 500 });
    }
  };
}
