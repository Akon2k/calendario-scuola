// Todo simulado: no lee Gmail real, no usa Groq ni modifica Supabase.
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';

const source = readFileSync('botscuola/BotScuola.gs', 'utf8');
const nuevoContexto = () => {
  const c = vm.createContext({ console: { log() {}, error() {} } });
  c.Date = class extends Date { static now() { return Date.parse('2026-10-16T23:59:59Z'); } };
  vm.runInContext(source, c);
  return c;
};
const ivan = 'ivancarmonavidal@gmail.com';
const mama = 'franciscaverasalazar@gmail.com';
const otro = 'otra.familia@example.org';
const scuola = 'Profesora <profesora@scuolaitalianadiconcepcion.cl>';
const lecturas = [];
const mensaje = ({ id = 'm1', from = scuola, to = ivan, cc = '', bcc = '',
                   fecha = '2026-10-16T12:00:00Z', body = 'Texto del comunicado' } = {}) => ({
  getId: () => id, getFrom: () => from, getTo: () => to, getCc: () => cc,
  getBcc: () => bcc, getDate: () => new Date(fecha), getSubject: () => 'Asunto ' + id,
  getPlainBody: () => { lecturas.push(id); return body; },
});

const casos = [
  ['sólo Iván', {}, false],
  ['sólo Francisca', { to: mama }, false],
  ['los dos padres', { to: ivan, cc: mama }, false],
  ['los dos padres en CCO', { to: '', bcc: `${ivan}, ${mama}` }, false],
  ['familia repetida y mayúsculas', { to: ivan.toUpperCase(), cc: `${ivan}, ${mama}` }, false],
  ['nombre con coma', { to: `"Carmona, Iván" <${ivan}>`, cc: mama }, false],
  ['email en nombre no es destinatario', { to: `"${otro}" <${ivan}>` }, false],
  ['otro apoderado en Para', { to: `${ivan}, ${otro}` }, true],
  ['otro apoderado en CC', { cc: `${mama}, ${otro}` }, true],
  ['otro apoderado en CCO visible', { bcc: otro }, true],
  ['copia a otra persona de la Scuola', { cc: 'direccion@scuolaitalianadiconcepcion.cl' }, true],
  ['una dirección de lista', { to: 'primero@scuolaitalianadiconcepcion.cl' }, true],
  ['CCO invisible no se adivina', { to: ivan, bcc: '' }, false],
  ['destinatarios ocultos', { to: 'undisclosed-recipients:;' }, false],
  ['sin destinatarios', { to: '' }, false],
  ['encabezado incompleto', { cc: 'sin dirección verificable' }, false],
  ['comillas sin cerrar', { cc: `"Nombre <${otro}>` }, false],
  ['otro remitente', { from: otro, cc: mama }, false],
  ['correo saliente', { from: ivan, to: 'profesora@scuolaitalianadiconcepcion.cl' }, false],
  ['dominio parecido', { from: 'profesora@falsascuolaitalianadiconcepcion.cl', cc: otro }, false],
  ['dominio con sufijo ajeno', { from: 'profesora@scuolaitalianadiconcepcion.cl.example.org', cc: otro }, false],
  ['dominio sólo en el nombre', { from: '"profesora@scuolaitalianadiconcepcion.cl" <ajeno@example.org>', cc: otro }, false],
  ['dominio en mayúsculas', { from: 'SCUOLA <PROFESORA@SCUOLAITALIANADICONCEPCION.CL>', cc: otro }, true],
];
const c = nuevoContexto();
for (const [nombre, datos, esperado] of casos) {
  assert.equal(c.esComunicado(mensaje(datos)), esperado, nombre);
  if (!esperado) assert.equal(c.publicarEnElCalendario(mensaje(datos), {}), false);
}
assert.deepEqual(lecturas, []);
c.Utilities = { formatDate: fecha => fecha.toISOString() };
c.Date = class extends Date { static now() { return Date.parse('2026-10-16T23:59:59Z'); } };
c.GmailApp = { search: () => [{ getMessages: () => casos.map(([, datos], i) => mensaje({ ...datos, id: 'caso' + i })) }] };
const revision = c.revisarFiltroCorreos();
assert.equal(revision.revisados, casos.filter(([, datos]) => c.esDeLaScuola(mensaje(datos))).length);
assert.equal(revision.conOtrosDestinatarios, casos.filter(([, , apto]) => apto).length);
assert.deepEqual(lecturas, [], 'la revisión opcional sólo lee encabezados');
console.log(`OK: ${casos.length} casos del filtro de destinatarios y remitente.`);

// El listado incluye los 9 correos, aunque sólo algunos cumplan la regla pública.
const listado = nuevoContexto();
const registro = [];
listado.console = { log: linea => registro.push(linea), error() {} };
listado.Utilities = { formatDate: fecha => fecha.toISOString() };
listado.Date = class extends Date { static now() { return Date.parse('2026-10-16T23:59:59Z'); } };
const nueve = Array.from({ length: 9 }, (_, i) => mensaje({
  id: 'octubre' + i,
  from: ['Inspectoria', 'Tamara', 'Valentina'][i % 3] +
    ' <' + ['inspectoria', 'tamara', 'valentina'][i % 3] + '@scuolaitalianadiconcepcion.cl>',
  cc: i % 2 ? otro : '', fecha: `2026-10-${String(i + 2).padStart(2, '0')}T12:00:00Z`,
}));
listado.GmailApp = { search: query => {
  assert.ok(query.startsWith('from:scuolaitalianadiconcepcion.cl after:'));
  assert.ok(!query.includes('-label:'));
  return [{ getMessages: () => [...nueve, nueve[0],
    mensaje({ fecha: '2026-08-31T19:00:00Z' }),
    mensaje({ fecha: '2026-10-17T19:00:00Z' }),
    mensaje({ from: ivan, cc: otro }),
  ] }];
} };
const conteo = listado.revisarFiltroCorreos();
assert.equal(conteo.revisados, 9);
assert.equal(conteo.conOtrosDestinatarios, 4);
assert.equal(conteo.omitidos, 0);
assert.equal(conteo.porContenido, 9);
assert.ok(['Inspectoria', 'Tamara', 'Valentina'].every(nombre => registro.some(linea => linea.includes(nombre))));
assert.ok(registro.some(linea => linea.includes('sólo Iván/Francisca visibles')));
assert.ok(!registro.join('\n').includes(otro), 'no imprime direcciones de otros apoderados');
assert.deepEqual(lecturas, [], 'listar no lee cuerpos ni usa IA, Sheets o Supabase');
console.log('OK: listado privado completo de los 9 correos, con remitente y motivo de exclusión.');

// Servicios simulados. No existe SpreadsheetApp: la web ya no depende de hojas.
const auto = nuevoContexto();
assert.ok(!/SpreadsheetApp|tieneAprobacion|hojaRevision/.test(source));
const props = new Map([['BOTSCUOLA_CLAVE', 'clave-ficticia-solo-pruebas']]);
auto.PropertiesService = { getScriptProperties: () => ({
  getProperty: k => props.get(k) || null,
  setProperty: (k, v) => props.set(k, v),
}) };
let bloqueado = false, liberaciones = 0;
auto.LockService = { getScriptLock: () => ({
  tryLock: () => !bloqueado,
  releaseLock: () => { liberaciones++; },
}) };
const mensajes = [
  mensaje({ id: 'personal' }),
  mensaje({ id: 'familia', cc: mama }),
  mensaje({ id: 'publico', cc: otro, body: 'Sólo texto del comunicado' }),
  mensaje({ id: 'anterior', cc: otro, fecha: '2026-08-31T23:59:59.999-04:00' }),
  mensaje({ id: 'guardado', cc: otro }),
  mensaje({ id: 'ajeno', from: otro, cc: mama }),
];
const hilo = { getMessages: () => mensajes };
const consultasGmail = [];
let privados = [];
auto.GmailApp = {
  search: (query, inicio, lote) => {
    consultasGmail.push(query);
    const lista = query.includes('-label:') ? privados.filter(h => !h.etiquetado) : [hilo];
    return lista.slice(inicio, inicio + lote);
  },
  getUserLabelByName: () => ({}),
};
auto.Utilities = { sleep() {} };
const base = new Map([['guardado', { id: 'guardado' }]]);
const requests = [], fallarPosts = new Set(), fallarIA = new Set();
let codigoLectura = 200;
auto.UrlFetchApp = { fetch: (url, options) => {
  requests.push({ url, options });
  if (options.method === 'post') {
    const fila = JSON.parse(options.payload);
    assert.equal(options.headers['x-botscuola-clave'], 'clave-ficticia-solo-pruebas');
    assert.equal('to' in fila || 'cc' in fila || 'bcc' in fila, false, 'no exponer destinatarios');
    if (fallarPosts.has(fila.id)) return { getResponseCode: () => 403, getContentText: () => '{}' };
    const existe = base.has(fila.id);
    base.set(fila.id, fila);
    return { getResponseCode: () => 201, getContentText: () => existe ? '[]' : JSON.stringify([fila]) };
  }
  const parsed = new URL(url);
  const offset = Number(parsed.searchParams.get('offset'));
  const limite = Number(parsed.searchParams.get('limit'));
  const filas = [...base.values()].sort((a, b) => a.id.localeCompare(b.id)).slice(offset, offset + limite);
  return { getResponseCode: () => codigoLectura, getContentText: () => JSON.stringify(filas) };
} };
const analizados = [], avisos = [], eventos = [];
auto.analizarTextoConIA = (asunto, cuerpo) => {
  analizados.push({ asunto, cuerpo });
  if (fallarIA.has(asunto.replace('Asunto ', ''))) return null;
  const esPersonal = ['personal', 'familia', 'personal2'].some(id => asunto === 'Asunto ' + id);
  return { clasificacion: { tipo: esPersonal ? 'personal' : 'general', confianza: 0.99, evidencia: cuerpo },
    resumen: { puntos_clave: [cuerpo], accion_requerida: '' }, eventos: [] };
};
auto.notificarDoble = datos => avisos.push(datos);
auto.gestionarEventoEnCalendario = evt => eventos.push(evt);

let resultado = auto.sincronizarComunicados();
assert.equal(resultado.publicados, 1);
assert.equal(resultado.existentes, 1);
assert.equal(resultado.omitidos, 4);
assert.deepEqual(lecturas, ['personal', 'familia', 'publico'], 'clasifica ambiguos, sin mezclar el hilo');
assert.deepEqual(analizados.map(a => a.cuerpo), ['Texto del comunicado', 'Texto del comunicado', 'Sólo texto del comunicado']);
assert.equal(avisos.length, 0, 'la carga histórica no reenvía WhatsApp/Telegram');
assert.equal(eventos.length, 0, 'la carga histórica no agenda en Calendar');
assert.equal(base.size, 2);
resultado = auto.sincronizarComunicados();
assert.equal(resultado.publicados, 0);
assert.equal(analizados.length, 3, 'no vuelve a usar IA para los existentes ni personales cacheados');
assert.deepEqual(lecturas, ['personal', 'familia', 'publico']);
for (const [key, valor] of props) {
  if (key.startsWith('BOTSCUOLA_OMITIDO_')) {
    assert.ok(!valor.includes('Texto') && !valor.includes('@'), 'no guarda texto ni personas en la caché');
  }
}

// Una respuesta nueva de la Scuola dentro del mismo hilo no queda oculta por etiquetas antiguas.
mensajes.push(mensaje({ id: 'respuesta', cc: otro }));
assert.equal(auto.sincronizarComunicados().publicados, 1);
assert.ok(base.has('respuesta'));
assert.ok(consultasGmail.every(q => !q.includes('-label:')));

mensajes.push(mensaje({ id: 'post-fallido', cc: otro }));
fallarPosts.add('post-fallido');
assert.equal(auto.sincronizarComunicados().fallidos, 1);
assert.ok(!base.has('post-fallido'));
fallarPosts.clear();
assert.equal(auto.sincronizarComunicados().publicados, 1, 'reintenta inserciones fallidas');
mensajes.push(mensaje({ id: 'ia-fallida', cc: otro }));
fallarIA.add('ia-fallida');
assert.equal(auto.sincronizarComunicados().fallidos, 1);
assert.ok(!base.has('ia-fallida'));
fallarIA.clear();
assert.equal(auto.sincronizarComunicados().publicados, 1, 'reintenta IA sin inventar eventos');

const lecturasAntes = lecturas.length;
codigoLectura = 503;
assert.throws(() => auto.sincronizarComunicados(), /503/);
codigoLectura = 200;
props.delete('BOTSCUOLA_CLAVE');
assert.throws(() => auto.sincronizarComunicados(), /BOTSCUOLA_CLAVE/);
props.set('BOTSCUOLA_CLAVE', 'clave-ficticia-solo-pruebas');
assert.equal(lecturas.length, lecturasAntes, 'si no puede consultar la tabla, no lee cuerpos');
const consultasAntes = requests.length;
bloqueado = true;
auto.sincronizarComunicados();
assert.equal(requests.length, consultasAntes, 'no solapa ejecuciones');
bloqueado = false;
assert.ok(liberaciones >= 9, 'libera bloqueo también al fallar');
console.log('OK: publicación automática sin hojas, sin duplicados, con reintentos y privacidad entre mensajes.');

// La función habitual del disparador alimenta la página y conserva los canales privados.
const reciente = mensaje({ id: 'reciente', cc: otro });
mensajes.push(reciente);
const privado = {
  getMessages: () => [reciente], etiquetado: false,
  addLabel() { this.etiquetado = true; },
};
privados = [privado];
const analisisAntes = analizados.length;
auto.procesarCorreosEscolares();
assert.ok(base.has('reciente'));
assert.equal(avisos.length, 1);
assert.equal(analizados.length, analisisAntes + 1, 'reutiliza el análisis para WhatsApp/Telegram');
auto.procesarCorreosEscolares();
assert.equal(avisos.length, 1, 'no repite avisos de los hilos etiquetados');
privados = [{ getMessages: () => [mensaje({ id: 'personal2' })], addLabel() {} }];
auto.procesarCorreosEscolares();
assert.ok(lecturas.includes('personal2'), 'lo analiza para decidir, pero no lo publica ni notifica');
assert.ok(!base.has('personal2'));
assert.equal(avisos.length, 1);
console.log('OK: el disparador existente sincroniza la tabla y mantiene WhatsApp/Telegram.');

const alInicio = mensaje({ cc: otro, fecha: '2026-09-01T00:00:00-04:00' });
const antesDelInicio = mensaje({ cc: otro, fecha: '2026-08-31T23:59:59.999-04:00' });
assert.equal(auto.enPeriodoComunicados(alInicio), true);
assert.equal(auto.enPeriodoComunicados(antesDelInicio), false);
assert.equal(auto.enPeriodoComunicados(mensaje({ fecha: '2026-10-17T00:00:00Z' })), false);
assert.equal(auto.publicarEnElCalendario(antesDelInicio, {}), false);
const inicios = [], querys = [];
auto.GmailApp.search = (query, inicio, lote) => {
  querys.push(query); inicios.push(inicio);
  return inicio === 0 ? Array.from({ length: lote }, () => ({})) : [{}];
};
let hilos = 0;
auto.paraCadaHiloComunicados(() => { hilos++; });
assert.deepEqual(inicios, [0, 50]);
assert.equal(hilos, 51);
const corte = Math.floor(new Date('2026-09-01T00:00:00-04:00').getTime() / 1000) - 1;
const hastaBusqueda = Math.floor(Date.parse('2026-10-16T23:59:59Z') / 1000) + 1;
assert.ok(querys.every(q => q.includes(`after:${corte}`) && q.includes(`before:${hastaBusqueda}`) && !q.includes('newer_than')));
for (let n = 0; n < 501; n++) base.set('extra' + n, { id: 'extra' + n });
codigoLectura = 206;
assert.equal(auto.idsComunicadosGuardados().size, base.size, 'pagina también los IDs de Supabase');
assert.ok(requests.filter(r => r.options.method !== 'post').every(r =>
  new URL(r.url).searchParams.get('fecha') === 'gte.2026-09-01T04:00:00.000Z'));
console.log('OK: desde el 01/09/2026 inclusive en Chile hasta hoy, sin fechas futuras ni IDs truncados.');

// Clasificación para los correos con CCO o sólo los padres visibles.
const contenido = nuevoContexto();
const diagnosticoContenido = [];
contenido.console = { log: linea => diagnosticoContenido.push(linea), error() {} };
const propsContenido = new Map([['BOTSCUOLA_CLAVE', 'clave-ficticia']]);
let escriturasCache = 0, analisisContenido = 0;
contenido.PropertiesService = { getScriptProperties: () => ({
  getProperty: k => propsContenido.get(k) || null,
  setProperty: (k, v) => { escriturasCache++; propsContenido.set(k, v); },
}) };
contenido.LockService = { getScriptLock: () => ({ tryLock: () => true, releaseLock() {} }) };
const cuerpoGeneral = 'Estimadas familias: este jueves las clases terminan a las 13:00 horas.';
const cuerpoPersonal = 'Estimada Francisca: solicito entrevista para conversar sobre su hija.';
const clasificacion = (tipo = 'general', confianza = 0.99, evidencia = cuerpoGeneral) =>
  ({ tipo, confianza, evidencia });
const resumen = c => ({ clasificacion: c,
  resumen: { puntos_clave: ['Resumen de prueba'], accion_requerida: '' }, eventos: [] });
const datosContenido = new Map([
  ['general-solo', resumen(clasificacion())],
  ['general-oculto', resumen(clasificacion())],
  ['3MS', resumen(clasificacion())],
  ['personal-solo', resumen(clasificacion('personal', 0.99, cuerpoPersonal))],
  ['dudoso', resumen(clasificacion('dudoso', 0.5))],
  ['confianza-baja', resumen(clasificacion('general', 0.5))],
  ['evidencia-inventada', resumen(clasificacion('general', 0.99, 'Una cita que no existe en el correo'))],
  ['copias-personales', resumen(clasificacion('personal', 0.99, cuerpoPersonal))],
]);
const correosContenido = [...datosContenido.keys()].map(id => ({
  ...mensaje({ id, to: id === 'general-oculto' ? 'undisclosed-recipients:;' : ivan,
    cc: id === 'copias-personales' ? 'convivencia@scuolaitalianadiconcepcion.cl' : '',
    body: ['personal-solo', 'copias-personales'].includes(id) ? cuerpoPersonal : cuerpoGeneral }),
  getSubject: () => id === '3MS' ? 'GIORNATA DEI COLORI 3MS' : 'Asunto ' + id,
}));
// Caso sintético, no reproduce nombres ni información privada del correo real.
const cuerpoIndividual = 'Estimados apoderados: informamos una situación que involucró a su hija, Alumna Ejemplo. Es una comunicación individual.';
const casoConCopias = mensaje({ id: 'caso-individual', fecha: '2026-09-24T19:13:00Z',
  cc: 'convivencia@scuolaitalianadiconcepcion.cl', body: cuerpoIndividual });
assert.equal(contenido.enPeriodoComunicados(casoConCopias), true, 'el caso de septiembre ahora entra en búsqueda');
correosContenido.push(casoConCopias);
assert.equal(contenido.esComunicado(casoConCopias), true, 'hay otro destinatario, pero eso no autoriza publicar');
assert.equal(contenido.aceptadoParaCompartir(casoConCopias, resumen(clasificacion('general', 0.99, cuerpoIndividual)), cuerpoIndividual), false);
assert.equal(contenido.publicarEnElCalendario(casoConCopias, resumen(clasificacion('general', 0.99, cuerpoIndividual)), cuerpoIndividual), false);
const guardadosContenido = new Map();
contenido.GmailApp = { search: () => [{ getMessages: () => correosContenido }] };
contenido.UrlFetchApp = { fetch: (url, options) => {
  if (options.method === 'post') {
    const fila = JSON.parse(options.payload);
    assert.ok(!('clasificacion' in fila), 'no publica evidencia ni contenido del clasificador');
    guardadosContenido.set(fila.id, fila);
    return { getResponseCode: () => 201, getContentText: () => '[]' };
  }
  return { getResponseCode: () => 200,
    getContentText: () => JSON.stringify([...guardadosContenido.keys()].map(id => ({ id }))) };
} };
contenido.analizarTextoConIA = (asunto, cuerpo, fecha) => {
  analisisContenido++;
  assert.notEqual(asunto, 'Asunto caso-individual', 'el bloqueo explícito ocurre antes de enviar a la IA');
  assert.ok(fecha.startsWith('2026-10-16'), 'pasa la fecha real del correo a la IA');
  return datosContenido.get(asunto === 'GIORNATA DEI COLORI 3MS' ? '3MS' : asunto.replace('Asunto ', ''));
};
const vista = contenido.previsualizarComunicados();
assert.equal(vista.aptos, 3);
assert.equal(vista.omitidos, 6);
assert.equal(vista.publicados, 0);
assert.equal(guardadosContenido.size, 0, 'previsualizar no inserta nada');
assert.equal(escriturasCache, 0, 'previsualizar tampoco cambia decisiones en caché');
const omitidosVista = diagnosticoContenido.filter(linea => linea.startsWith('OMITIDO POR CONTENIDO'));
assert.equal(omitidosVista.length, 5);
assert.ok(omitidosVista.every(linea => linea.includes('"motivo":') && linea.includes('"confianza":')));
assert.ok(!diagnosticoContenido.join('\n').includes(cuerpoPersonal), 'no imprime el cuerpo personal ni la cita');
assert.ok(!diagnosticoContenido.join('\n').includes('Una cita que no existe'), 'no imprime la evidencia inventada');
const carga = contenido.sincronizarComunicados();
assert.equal(carga.publicados, 3);
assert.ok(guardadosContenido.has('general-solo'));
assert.ok(guardadosContenido.has('general-oculto'));
assert.ok(guardadosContenido.has('3MS'), 'no filtra por curso o siglas');
for (const id of ['personal-solo', 'dudoso', 'confianza-baja', 'evidencia-inventada', 'copias-personales', 'caso-individual']) {
  assert.ok(!guardadosContenido.has(id), id);
}
const hechos = analisisContenido;
contenido.sincronizarComunicados();
assert.equal(analisisContenido, hechos, 'los descartados no se mandan a Groq cada 15 minutos');
assert.equal(contenido.generalConfirmado(resumen(clasificacion('general', '0.99')), cuerpoGeneral), false);
assert.equal(contenido.generalConfirmado(resumen(clasificacion('general', NaN)), cuerpoGeneral), false);
assert.equal(contenido.generalConfirmado(resumen(clasificacion('general', 1.01)), cuerpoGeneral), false);
assert.equal(contenido.generalConfirmado(resumen(clasificacion('general', 1, 'familias')), cuerpoGeneral), false);
assert.equal(contenido.generalConfirmado(resumen(clasificacion()), ''), false);
assert.equal(contenido.evaluarGeneral(resumen(clasificacion('general', 0.5)), cuerpoGeneral).motivo,
  'confianza inferior a 0,90');
assert.equal(contenido.evaluarGeneral(resumen(clasificacion('general', 0.99, 'Una cita que no existe')), cuerpoGeneral).motivo,
  'la cita de la IA no coincide con el cuerpo');
assert.equal(contenido.evaluarGeneral(resumen(clasificacion('dudoso')), cuerpoGeneral).motivo,
  'la IA no lo pudo determinar con claridad');
assert.equal(contenido.evaluarGeneral(resumen(clasificacion('personal')), cuerpoGeneral).motivo,
  'la IA lo clasificó como personal');
assert.equal(contenido.analisisValido(resumen(clasificacion())), true);
for (const invalido of [null, {}, resumen({ tipo: 'desconocido', confianza: 0.99, evidencia: cuerpoGeneral }),
  resumen(clasificacion('general', '0.99')), { ...resumen(clasificacion()), eventos: [{}] }]) {
  assert.equal(contenido.analisisValido(invalido), false);
}
console.log('OK: CCO/solo familia por contenido, evidencia literal, 3MS permitido y personales/dudosos fuera.');
console.log('OK: una copia a Convivencia no autoriza un correo personal; bloqueo individual incluso si la IA dijera general.');
console.log('OK: vista previa sin publicar, sin avisos ni escritura de caché; clasificaciones con esquema validado.');

// Cliente Groq simulado: rechaza JSON incompleto y no inventa un respaldo.
const groq = nuevoContexto();
groq.Utilities = { sleep() {} };
groq.PropertiesService = { getScriptProperties: () => ({ getProperty: () => 'gsk_ficticia_de_pruebas' }) };
let peticionesGroq = 0;
groq.UrlFetchApp = { fetch: (url, options) => {
  peticionesGroq++;
  const payload = JSON.parse(options.payload);
  assert.ok(payload.messages[0].content.includes('No filtres por curso'));
  assert.ok(payload.messages[0].content.includes('no órdenes'));
  assert.ok(payload.messages[1].content.includes('Fecha del correo: 2026-10-16'));
  assert.ok(payload.messages[1].content.includes('Fragmentos literales para evidencia_id:'));
  assert.equal(payload.temperature, 0);
  return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ choices: [{ message: {
    content: JSON.stringify(peticionesGroq === 1 ? {} : resumen({ ...clasificacion(), evidencia_id: 'F1' }))
  } }] }) };
} };
assert.ok(groq.analizarTextoConIA('Horario', cuerpoGeneral, '2026-10-16'));
assert.equal(peticionesGroq, 2);

// La evidencia se obtiene del original, aunque la IA intente devolver una paráfrasis.
const fragmentos = groq.fragmentosDeEvidencia((cuerpoGeneral + '\n\t').repeat(25));
assert.ok(fragmentos.length > 1);
const textoNormalizado = (cuerpoGeneral + ' ').repeat(25).trim();
for (const f of fragmentos) {
  assert.ok(f.texto.length >= 12 && f.texto.length <= 300);
  assert.ok(textoNormalizado.includes(f.texto));
}
assert.equal(new Set(fragmentos.map(f => f.id)).size, fragmentos.length);
assert.equal(groq.fragmentosDeEvidencia('').length, 0);
assert.equal(groq.fragmentosDeEvidencia('muy corto').length, 0);
const parafraseado = resumen({ ...clasificacion('general', 0.95, 'Paráfrasis inventada por la IA'), evidencia_id: 'F1' });
assert.equal(groq.resolverEvidencia(parafraseado, fragmentos), true);
assert.equal(parafraseado.clasificacion.evidencia, fragmentos[0].texto);
assert.equal(groq.generalConfirmado(parafraseado, textoNormalizado), true);
for (const id of ['F99999', 1, null, undefined]) {
  assert.equal(groq.resolverEvidencia(resumen({ ...clasificacion(), evidencia_id: id }), fragmentos), false);
}
assert.equal(groq.resolverEvidencia(resumen({ tipo: 'personal', confianza: 0.99, evidencia_id: 'F1' }), fragmentos), true);
assert.equal(groq.resolverEvidencia(resumen({ tipo: 'personal', confianza: 0.99 }), fragmentos), false);
assert.equal(groq.resolverEvidencia(resumen({ tipo: 'dudoso', confianza: 0.5, evidencia_id: null }), []), true);
groq.UrlFetchApp.fetch = () => ({ getResponseCode: () => 200, getContentText: () => '{"choices":[{"message":{"content":"{}"}}]}' });
assert.equal(groq.analizarTextoConIA('Horario', cuerpoGeneral), null);
console.log('OK: cascada de Groq con validación y sin evento ficticio si falla.');
console.log('OK: evidencia extraída del original por ID, sin citas parafraseadas ni IDs inventados.');

// Diagnósticos seguros: nunca registrar contenido bruto del proveedor o excepciones.
const trazasGroq = [];
groq.console = { log: linea => trazasGroq.push(linea), error: linea => trazasGroq.push(linea) };
const secretoSimulado = 'CONTENIDO_PRIVADO_Y_TOKEN_FICTICIO';
for (const [codigo, respuesta, motivo] of [
  [429, secretoSimulado, 'límite de solicitudes o cuota alcanzado'],
  [401, secretoSimulado, 'autenticación rechazada'],
  [404, secretoSimulado, 'modelo o recurso no disponible'],
  [503, secretoSimulado, 'fallo del proveedor'],
  [200, secretoSimulado, 'respuesta HTTP sin JSON válido'],
  [200, JSON.stringify({ choices: [{ message: { content: secretoSimulado } }] }), 'el modelo devolvió JSON inválido'],
  [200, JSON.stringify({ choices: [{ message: { content: '{}' } }] }), 'clasificación, evidencia o estructura inválida'],
  [200, '{}', 'respuesta sin resultado del modelo'],
]) {
  vm.runInContext('ESTADO_GROQ.pausas = {};', groq);
  groq.UrlFetchApp.fetch = () => ({ getResponseCode: () => codigo, getContentText: () => respuesta });
  const diagnostico = {};
  assert.equal(groq.analizarTextoConIA('Horario', cuerpoGeneral, '', diagnostico), null);
  assert.equal(diagnostico.intentos.length, 2);
  assert.ok(diagnostico.intentos.every(i => i.modelo && i.motivo === motivo));
  if (codigo !== 200) assert.ok(diagnostico.intentos.every(i => i.http === codigo));
  assert.ok(!JSON.stringify(diagnostico).includes(secretoSimulado));
}
groq.UrlFetchApp.fetch = () => { throw new Error(secretoSimulado); };
const errorConexion = {};
assert.equal(groq.analizarTextoConIA('Horario', cuerpoGeneral, '', errorConexion), null);
assert.ok(errorConexion.intentos.every(i => i.motivo.includes('conexión')));
assert.ok(!trazasGroq.join('\n').includes(secretoSimulado));
groq.PropertiesService = { getScriptProperties: () => ({ getProperty: () => null }) };
const sinClave = {};
assert.equal(groq.analizarTextoConIA('Horario', cuerpoGeneral, '', sinClave), null);
assert.equal(sinClave.intentos.length, 1);
assert.ok(sinClave.intentos[0].motivo.includes('GROQ_API_KEY'));

// Vista previa real del cliente simulado: identifica cada pendiente sin escribir nada.
const pendientes = nuevoContexto();
pendientes.Utilities = { sleep() {} };
const logPendientes = [];
pendientes.console = { log: linea => logPendientes.push(linea), error: linea => logPendientes.push(linea) };
pendientes.LockService = { getScriptLock: () => ({ tryLock: () => true, releaseLock() {} }) };
pendientes.PropertiesService = { getScriptProperties: () => ({
  getProperty: k => k === 'GROQ_API_KEY' ? 'gsk_ficticia_de_pruebas' :
    k === 'BOTSCUOLA_CLAVE' ? 'clave-ficticia' : null,
  setProperty: () => assert.fail('la vista previa no escribe propiedades'),
}) };
pendientes.GmailApp = { search: () => [{ getMessages: () => [
  mensaje({ id: 'pendiente1', body: secretoSimulado }),
  mensaje({ id: 'pendiente2', body: secretoSimulado }),
] }] };
let solicitudesPendientes = 0;
pendientes.UrlFetchApp = { fetch: (url, options) => {
  if (url.includes('api.groq.com')) {
    solicitudesPendientes++;
    return { getResponseCode: () => 429, getContentText: () => secretoSimulado };
  }
  assert.notEqual(options.method, 'post', 'no inserta comunicados en vista previa');
  return { getResponseCode: () => 200, getContentText: () => '[]' };
} };
const vistaPendientes = pendientes.previsualizarComunicados();
assert.equal(vistaPendientes.fallidos, 2);
assert.equal(vistaPendientes.publicados, 0);
const detallePendientes = logPendientes.filter(l => l.startsWith('PENDIENTE · '))
  .map(l => JSON.parse(l.slice('PENDIENTE · '.length)));
assert.equal(detallePendientes.length, 2);
assert.ok(detallePendientes.every((d, i) => d.asunto === 'Asunto pendiente' + (i + 1)
  && d.fecha === '2026-10-16T12:00:00.000Z'
  && d.gmail === 'https://mail.google.com/mail/u/0/#all/pendiente' + (i + 1)
  && d.intentos.length === 2 && d.intentos.every(intento => intento.http === 429)));
assert.equal(solicitudesPendientes, 2, 'el segundo correo no repite solicitudes a modelos en pausa');
assert.ok(detallePendientes[1].intentos.every(i => i.motivo.includes('en pausa') && i.reintentarDesde));
assert.ok(!logPendientes.join('\n').includes(secretoSimulado));
console.log('OK: pendientes identificados por asunto, fecha, Gmail y diagnóstico seguro; sin publicar ni registrar cuerpos/tokens.');

// Ritmo y reintentos con reloj simulado: no duerme ni usa servicios reales.
const ritmo = nuevoContexto();
let reloj = Date.parse('2026-10-16T20:00:00Z');
const esperas = [], llamadasRitmo = [];
ritmo.Date = class extends Date { static now() { return reloj; } };
ritmo.Utilities = { sleep: ms => { esperas.push(ms); reloj += ms; } };
ritmo.PropertiesService = { getScriptProperties: () => ({ getProperty: () => 'gsk_ficticia_de_pruebas' }) };
let limitarPrincipal = false;
ritmo.UrlFetchApp = { fetch: (url, opciones) => {
  const { model } = JSON.parse(opciones.payload);
  assert.ok(['openai/gpt-oss-20b', 'openai/gpt-oss-120b'].includes(model), 'no llama los modelos con 404');
  llamadasRitmo.push({ modelo: model, cuando: reloj });
  if (limitarPrincipal && model === 'openai/gpt-oss-20b') return {
    getResponseCode: () => 429, getContentText: () => secretoSimulado,
    getAllHeaders: () => ({ 'Retry-After': '120' }),
  };
  return { getResponseCode: () => 200, getContentText: () => JSON.stringify({ choices: [{ message: {
    content: JSON.stringify(resumen({ ...clasificacion(), evidencia_id: 'F1' }))
  } }] }) };
} };
assert.ok(ritmo.analizarTextoConIA('Horario', cuerpoGeneral));
assert.ok(ritmo.analizarTextoConIA('Horario', cuerpoGeneral));
limitarPrincipal = true;
assert.ok(ritmo.analizarTextoConIA('Horario', cuerpoGeneral));
const antesDelReintento = llamadasRitmo.length;
const diagPausa = {};
assert.ok(ritmo.analizarTextoConIA('Horario', cuerpoGeneral, '', diagPausa));
assert.equal(llamadasRitmo.length, antesDelReintento + 1, 'sólo consulta el respaldo durante Retry-After');
assert.ok(diagPausa.intentos[0].motivo.includes('en pausa'));
assert.ok(llamadasRitmo.slice(1).every((l, i) => l.cuando - llamadasRitmo[i].cuando >= 7000));
assert.ok(esperas.every(ms => ms === 7000));
const llamadasAntesDelLimite = llamadasRitmo.length;
const diagLimite = { limiteTiempo: reloj + 6000 };
assert.equal(ritmo.analizarTextoConIA('Horario', cuerpoGeneral, '', diagLimite), null);
assert.equal(llamadasRitmo.length, llamadasAntesDelLimite, 'no duerme más allá del tiempo de seguridad');
assert.ok(diagLimite.intentos.some(i => i.motivo.includes('tiempo de seguridad')));
reloj += 120000;
limitarPrincipal = false;
assert.ok(ritmo.analizarTextoConIA('Horario', cuerpoGeneral));
assert.equal(llamadasRitmo.at(-1).modelo, 'openai/gpt-oss-20b', 'reintenta tras caducar la pausa');
assert.equal(ritmo.pausaSolicitadaGroq({}), 60000);
assert.equal(ritmo.pausaSolicitadaGroq({ getAllHeaders: () => ({ 'retry-after': 'no válido' }) }), 60000);
assert.equal(ritmo.pausaSolicitadaGroq({ getAllHeaders: () => ({ 'RETRY-AFTER': '0.5' }) }), 1000);
assert.equal(ritmo.pausaSolicitadaGroq({ getAllHeaders: () => ({ 'Retry-After': new Date(reloj + 120000).toUTCString() }) }), 120000);
console.log('OK: sólo modelos que respondieron, solicitudes espaciadas, pausa tras 429 y Retry-After sin exceder el tiempo de seguridad.');
