// Ejecuta el JavaScript de salida/calendario_evaluaciones.html contra un DOM
// simulado: comprueba que pinta el mes, que los clics funcionan, que el botón
// «Descargar .ics» entrega exactamente el .ics incrustado, que los resúmenes
// que calcula el JavaScript coinciden con los de Python y que el editor de la
// comunidad (nuevo evento, corrección remota y deshacer) manda lo correcto a
// Supabase.
import { readFileSync } from "node:fs";
import { URL as URLReal } from "node:url";

const html = readFileSync("salida/calendario_evaluaciones.html", "utf8");

const porId = {};

// ---------- DOM mínimo ----------
class Elem {
  constructor(tag) {
    this.tagName = tag;
    this.children = [];
    this.className = "";
    this.dataset = {};
    this.textContent = "";
    this.title = "";
    this.listeners = {};
    this._html = "";
    this._id = "";
    this.style = {
      props: {},
      setProperty(k, v) { this.props[k] = v; },
    };
  }
  get id() { return this._id; }
  set id(v) { this._id = v; if (v) porId[v] = this; }   // getElementById por id
  get innerHTML() { return this._html; }
  set innerHTML(v) { this._html = String(v); this.children = []; }
  appendChild(c) { this.children.push(c); return c; }
  addEventListener(t, fn) { (this.listeners[t] ||= []).push(fn); }
  remove() {}
  click() { (this.listeners.click || []).forEach((fn) => fn({ currentTarget: this })); }
  set href(v) { this._href = v; }
  get href() { return this._href; }
  set download(v) { this._dl = v; }
  get download() { return this._dl; }
}

for (const id of ["datos", "ics-b64", "nube", "mes-actual", "rejilla", "detalle",
                  "leyenda", "anterior", "siguiente", "hoy", "imprimir",
                  "descargar", "nuevo", "nube-estado", "modal", "m-titulo",
                  "m-autor", "m-campos", "m-error", "m-cancelar", "m-guardar",
                  "instalar", "avisos", "probar", "avisos-estado",
                  "pestanas", "tab-calendario", "tab-mensajes",
                  "cuenta-mensajes", "vista-calendario", "mensajes",
                  "mensajes-lista"]) {
  const el = new Elem("div");
  el.id = id;
  porId[id] = el;
  if (id === "datos" || id === "ics-b64" || id === "nube") {
    const mm = html.match(new RegExp(`id="${id}">([\\s\\S]*?)</script>`));
    if (!mm) throw new Error(`no encontré #${id}`);
    el.textContent = mm[1].trim();
  }
}

// el DOM simulado no parsea el HTML: se copian los «hidden» de la maqueta
porId["tab-mensajes"].hidden = /<button id="tab-mensajes"[^>]*hidden/.test(html);
porId["mensajes"].hidden = /<section id="mensajes"[^>]*hidden/.test(html);

let descargado = null;
globalThis.document = {
  getElementById: (id) => porId[id],
  createElement: (tag) => new Elem(tag),
  createTextNode: (t) => ({ nodeValue: t }),
  body: new Elem("body"),
};
globalThis.window = { print: () => {} };
globalThis.URL = {
  createObjectURL: (blob) => { descargado = blob; return "blob:falsa"; },
  revokeObjectURL: () => {},
};

// ---------- Supabase simulado ----------
// filasSim = lo que "hay en la nube"; posts = lo que la página envió.
const filasSim = [];
const posts = [];
// la tabla «comunicados» (los correos de la Scuola) va aparte de las correcciones
const comunicadosSim = [
  { id: "c1", asunto: "3ª Reunión de Apoderados", fecha: "2026-10-15T18:40:00Z",
    puntos: ["Miércoles 21 a las 18:30 en la Scuola."],
    accion: "Asistir puntualmente.",
    eventos: [{ titulo: "Reunión de Apoderados",
                fecha_inicio: "2026-10-21T18:30:00" }] },
  { id: "c2", asunto: "Informe de notas", fecha: "2026-10-09T12:05:00Z",
    puntos: ["Se entrega el lunes 26 por la intranet."], accion: "", eventos: [] },
];
const consultasMensajes = [];
let errorMensajes = false;
globalThis.fetch = async (url, opts = {}) => {
  // cada tabla tiene su propio simulacro
  const comu = String(url).indexOf("/comunicados") >= 0;
  const lista = comu ? comunicadosSim : filasSim;
  const hechos = comu ? [] : posts;
  if (comu) {
    const consulta = new URLReal(url);
    consultasMensajes.push(consulta.searchParams);
    if (errorMensajes) return { ok: false, status: 503 };
    const offset = Number(consulta.searchParams.get('offset') || 0);
    const limite = Number(consulta.searchParams.get('limit') || 1000);
    return { ok: true, status: 200, json: async () => lista.slice(offset, offset + limite) };
  }
  if (opts && opts.method === "POST") {
    const cuerpo = JSON.parse(opts.body);
    if (comu && lista.some((f) => f.id === cuerpo.id))   // clave primaria
      return { ok: true, status: 200, text: async () => "[]" };
    const fila = { id: "f" + (hechos.length + 1),
                   creado: new Date().toISOString(), ...cuerpo };
    lista.push(fila);
    hechos.push(fila);
    return { ok: true, status: 201, text: async () => JSON.stringify([fila]) };
  }
  return { ok: true, status: 200,
           json: async () => [...lista],
           text: async () => JSON.stringify(lista) };
};

// ---------- ejecutar el script de la página ----------
const i = html.lastIndexOf("<script>");
const j = html.indexOf("</script>", i);
const js = html.slice(i + "<script>".length, j);
eval(js);
await new Promise((r) => setTimeout(r, 30));   // la carga de la nube es async

const fallo = (msg) => { console.error("FALLO: " + msg); process.exit(1); };
const ok = (msg) => console.log("  ok  " + msg);

// la sección de instrucciones existe y el pie no nombra la carpeta de Outlook
if (!/id="ayuda"/.test(html) || !html.includes("Instrucciones de uso"))
  fallo("falta la sección «Instrucciones de uso» (#ayuda)");
if (!html.includes("Android") || !html.includes("iPhone")
    || !html.includes("Agregar a pantalla de inicio")
    || !html.includes("Safari"))
  fallo("faltan los pasos de instalación para Android/iPhone");
ok("sección: Instrucciones de uso + pasos Android/iPhone");
const pie = (html.match(/<footer>([\s\S]*?)<\/footer>/) || [])[1] || "";
if (!pie) fallo("no encontré el pie de la página");
if (pie.includes("Scuola Rafaela"))
  fallo("el pie no debe nombrar la carpeta de Outlook");
ok("pie sin el nombre de la carpeta");

// el cuadro del detalle se estira a la altura del calendario (todo cuadrado)
const reglaMain = (html.match(/\bmain\s*{[^}]*}/) || [])[0] || "";
if (!/align-items:\s*stretch/.test(reglaMain))
  fallo("el detalle debe estirarse a la altura del calendario: " + reglaMain);
ok("detalle emparejado con la altura del calendario");
const tick = () => new Promise((r) => setTimeout(r, 30));
const itemDe = (caja, asig) => caja.children.find(
  (c) => c.children && c.children[0] && c.children[0].textContent === asig);
const barraDe = (item) => item && item.children.find(
  (c) => c.className === "acciones-item");

// Las fechas y los conteos salen de los datos embebidos: la escuela suma,
// borra y renumera evaluaciones (el 10-10-2026 quitó tres de Italiano), así
// que el test no puede depender de una fecha ni de un total concretos.
const datos = JSON.parse(porId.datos.textContent);
const oct = datos.eventos.filter((e) => e.f.startsWith("2026-10-"));
const FECHA_EV = oct.length ? oct[0].f : null;
const EV = oct.length ? oct[0] : null;
const LIBRE = (() => {
  for (let d = 17; d <= 31; d++) {
    const f = "2026-10-" + String(d).padStart(2, "0");
    if (!datos.eventos.some((e) => e.f === f)) return f;
  }
  return null;
})();
const RESUMEN = datos.resumenes.find((r) => r.f === "2026-10-10")
             || datos.resumenes.find((r) => r.f.startsWith("2026-10-"));
if (!FECHA_EV) fallo("no hay ninguna evaluación en octubre en los datos");
if (!LIBRE) fallo("no queda ningún día libre en octubre para el alta de prueba");
if (!RESUMEN) fallo("no hay resumen de sábado en octubre");
if (LIBRE === FECHA_EV) fallo("el día libre y el día con evaluación coinciden");

// 1) pintado inicial
if (porId["mes-actual"].textContent !== "Octubre 2026")
  fallo("mes inicial: " + porId["mes-actual"].textContent);
ok("mes inicial: " + porId["mes-actual"].textContent);

const celdas = porId.rejilla.children;
if (celdas.length !== 35) fallo("celdas de octubre: " + celdas.length);
ok("rejilla de octubre: 35 celdas");

const cEv = celdas.find((c) => c.dataset.fecha === FECHA_EV);
if (!cEv) fallo("no está la celda del " + FECHA_EV);
if (!cEv.children.some((h) => h.className === "ev resumen"
                              || (h.className || "").includes("ev")))
  fallo("la celda del " + FECHA_EV + " no tiene eventos");
ok(FECHA_EV + ": " + cEv.children.filter(
  (h) => (h.className || "").includes("ev")).length + " chips");

// 2) clic en el sábado con resumen (sólo resumen)
const cSab = celdas.find((c) => c.dataset.fecha === RESUMEN.f);
if (!cSab) fallo("no está la celda del sábado " + RESUMEN.f);
cSab.click();
const det = porId.detalle;
if (det.children.length !== 2 || det.children[1].className !== "caja-resumen")
  fallo("detalle del " + RESUMEN.f + ": "
        + det.children.map((c) => c.className).join(","));
if (!det.children[1].children[0].textContent.includes(RESUMEN.e))
  fallo("resumen: " + det.children[1].children[0].textContent);
const preSab = det.children[1].children[1];
const fechas = preSab.textContent.split("\n\n");
const esperadas = RESUMEN.c.split("\n\n").length;
if (fechas.length !== esperadas || fechas.some((f) => !f.trim()))
  fallo("el resumen debe separar las " + esperadas
        + " fechas con línea en blanco: "
        + JSON.stringify(preSab.textContent));
ok("clic en sábado " + RESUMEN.f + " -> resumen: "
   + det.children[1].children[0].textContent);
ok("   línea en blanco entre las " + esperadas + " fechas ("
   + (fechas.length - 1) + " saltos)");

// 3) clic en cada fecha de octubre con evaluación: los mismos campos que los
//    diálogos de la fuente («Detalle de evaluación» y «de sub-evaluación»)
const nombreDe = (e) => String(e.e || "")
  .replace(/^(?:E|SE)\d+(?:-\d+)?:\s*/, "").trim();

let comprobadas = 0;
let subVistas = 0;
let ejemplo = "";
for (const ev of datos.eventos.filter((e) => e.f.startsWith("2026-10-"))) {
  const celda = celdas.find((c) => c.dataset.fecha === ev.f);
  if (!celda) { fallo("no está la celda del " + ev.f); break; }
  celda.click();

  const delDia = datos.eventos.filter((e) => e.f === ev.f).length;
  if (det.children.length !== delDia)
    fallo("detalle del " + ev.f + ": " + det.children.length
          + " bloques y " + delDia + " evaluaciones");

  const item = itemDe(det, ev.a);
  if (!item) { fallo("no aparece " + ev.a + " el " + ev.f); break; }
  const tit = item.children[1].textContent;
  const meta = item.children[2].textContent;
  const numero = String(ev.n || "").trim();
  const partes = numero.split(".");
  const esSub = /Sub/.test(String(ev.t || ""));

  // el nombre va solo: sin el «SE4-1:» de la lista ni el «(N° 4.1)» de antes
  if (tit !== nombreDe(ev))
    fallo("título del " + ev.f + ": " + JSON.stringify(tit)
          + " esperado " + JSON.stringify(nombreDe(ev)));
  if (numero && !meta.includes("Número " + (esSub ? partes[0] : numero)))
    fallo("falta el Número el " + ev.f + ": " + meta);
  if (esSub) {
    subVistas++;
    if (!meta.includes("Sub-número " + partes[1]))
      fallo("la sub-evaluación debe listar el Sub-número el " + ev.f
            + ": " + meta);
  }
  if (ev.p && !meta.includes("Prof")) fallo("falta el profesor el " + ev.f + ": " + meta);
  if (ev.co && !meta.includes("coef.")) fallo("falta el coeficiente el " + ev.f + ": " + meta);
  if (/ponderación|Sub-evaluación|^Evaluación$/m.test(meta))
    fallo("sobra la ponderación o la línea de tipo el " + ev.f + ": " + meta);
  // un ítem, un salto: sólo los campos con valor, cada uno en su línea
  const lineas = meta.split("\n").filter((l) => l.trim());
  const esperadas = (ev.p ? 1 : 0) + (ev.co ? 1 : 0)
                  + (numero ? (esSub ? 2 : 1) : 0);
  if (lineas.length !== esperadas)
    fallo("un item por linea el " + ev.f + " (" + esperadas + " esperadas): "
          + JSON.stringify(meta));

  if (!ejemplo) ejemplo = item.children[0].textContent + " · " + tit + " · "
    + meta.split("\n").join(" > ");
  comprobadas++;
}
if (!subVistas)
  console.log("  aviso: no hay sub-evaluaciones en octubre, no se probó el Sub-número");
ok("detalle: " + comprobadas + " evaluaciones de octubre con los campos de la "
   + "fuente (" + subVistas + " sub-evaluaciones con Número y Sub-número)");
ok("   por ejemplo: " + ejemplo);

// 4) navegación de meses
porId.siguiente.click();
if (porId["mes-actual"].textContent !== "Noviembre 2026")
  fallo("siguiente: " + porId["mes-actual"].textContent);
porId.anterior.click();
porId.anterior.click();
if (porId["mes-actual"].textContent !== "Septiembre 2026")
  fallo("anterior: " + porId["mes-actual"].textContent);
porId.hoy.click();
if (porId["mes-actual"].textContent !== "Octubre 2026")
  fallo("hoy: " + porId["mes-actual"].textContent);
ok("navegación: sig/anter/hoy");

// 5) leyenda
const nAsignaturas = new Set(Object.keys(datos.colores).map(a =>
  a.trim().replace(/\s+/g, ' ').toUpperCase())).size;
if (!porId.leyenda.children.length
    || porId.leyenda.children.length !== nAsignaturas)
  fallo("leyenda: " + porId.leyenda.children.length + " de " + nAsignaturas);
ok("leyenda: " + nAsignaturas + " asignaturas");
const reglaLeyenda = (html.match(/#leyenda\s*{[^}]*}/) || [])[0] || "";
if (!/justify-content:\s*flex-start/.test(reglaLeyenda))
  fallo("la leyenda debe quedar compacta: " + reglaLeyenda);
const nombresLeyenda = porId.leyenda.children.map(el => el.children[1].nodeValue);
if (!nombresLeyenda.includes("Lenguaje") || nombresLeyenda.includes("LENGUAJE Y COMUNICACIÓN"))
  fallo("la leyenda debe usar nombres cortos: " + nombresLeyenda);
ok("leyenda compacta, nombres cortos y sin duplicados");

// 6) descarga del .ics
porId.descargar.click();
if (!descargado) fallo("no se descargó nada");
const bytes = Buffer.from(await descargado.arrayBuffer());
const b64 = porId["ics-b64"].textContent.trim();
if (bytes.toString("base64") !== b64) fallo("el .ics descargado no coincide con el incrustado");
const texto = bytes.toString("utf8");
const eventos = (texto.match(/BEGIN:VEVENT/g) || []).length;
const icsEsperado = datos.eventos.length + datos.resumenes.length;
if (eventos !== icsEsperado)
  fallo("eventos descargados: " + eventos + " y esperados " + icsEsperado);
ok("descarga .ics: " + eventos + " eventos (" + datos.eventos.length
   + " evaluaciones + " + datos.resumenes.length + " resúmenes), "
   + "idéntico al incrustado");
if (!/download = 'Evaluacion Scuola\.ics'/.test(html))
  fallo("el .ics debe descargarse como «Evaluacion Scuola.ics»");
ok("nombre del archivo: Evaluacion Scuola.ics");

// 7) la nube está viva y los resúmenes del JS son los de Python
if (!porId["nube-estado"].textContent.includes("0 correcciones"))
  fallo("estado de la nube: " + porId["nube-estado"].textContent);
ok("nube conectada: " + porId["nube-estado"].textContent);

if (!Array.isArray(datos.paleta) || !datos.paleta.length)
  fallo("falta la paleta en el JSON");
const gen = globalThis.window.__calendario.resumenes();
if (gen.length !== datos.resumenes.length)
  fallo(`resúmenes: ${gen.length} generados vs ${datos.resumenes.length} embebidos`);
for (let n = 0; n < gen.length; n++) {
  const a = gen[n], b = datos.resumenes[n];
  if (a.k !== b.k || a.f !== b.f || a.e !== b.e || a.c !== b.c)
    fallo(`resumen ${n} difiere:\n  js: ${JSON.stringify(a)}\n  py: ${JSON.stringify(b)}`);
}
ok("los " + gen.length + " resúmenes calculados en JS coinciden con los de Python");

// 8) el modal agrega un evento nuevo a Supabase y aparece en la rejilla
if (porId.nuevo.hidden) fallo("el botón «nuevo» está oculto habiendo nube");
porId.nuevo.click();
if (porId.modal.hidden) fallo("el modal no se abrió");
if (porId["m-campos"].children.length < 10)
  fallo("el modal no cargó los campos: " + porId["m-campos"].children.length);
for (const c of ["FECHA", "ASIGNATURA", "EVALUACION", "NUMERO", "PROFESOR",
                 "CONTENIDO", "TIPO"]) {
  if (!porId["m-" + c]) fallo("falta el campo " + c);
}
porId["m-autor"].value = "Rafaela";
porId["m-FECHA"].value = LIBRE;
porId["m-ASIGNATURA"].value = "MATEMÁTICA";
porId["m-EVALUACION"].value = "Prueba agregada por la página";
porId["m-NUMERO"].value = "T9";
porId["m-PROFESOR"].value = "Prof. Prueba";
porId["m-guardar"].click();
await tick();

if (!posts.length) fallo("no se envió nada a Supabase");
const alta = posts[posts.length - 1];
if (alta.tipo !== "nuevo") fallo("tipo del alta: " + alta.tipo);
if (alta.clave !== "MATEMÁTICA|T9|EVALUACIÓN#1") fallo("clave del alta: " + alta.clave);
if (alta.autor !== "Rafaela") fallo("autor del alta: " + alta.autor);
if (alta.campos.FECHA !== LIBRE) fallo("fecha del alta: " + alta.campos.FECHA);
if (!porId.modal.hidden) fallo("el modal no se cerró al guardar");
ok("alta enviada: " + alta.clave + " · " + alta.autor);

const cLibre = porId.rejilla.children.find((c) => c.dataset.fecha === LIBRE);
if (!cLibre) fallo("no está la celda del " + LIBRE);
cLibre.click();
const detLibre = porId.detalle;
const itemNuevo = itemDe(detLibre, "MATEMÁTICA");
if (!itemNuevo) fallo("el evento nuevo no aparece el " + LIBRE + ": "
                      + detLibre.children.map((c) => c.className).join(","));
ok("evento nuevo visible el " + LIBRE + " oct ("
   + itemNuevo.children[1].textContent + ")");

// 9) una corrección de otra persona aparece, con su autor, y se puede deshacer
filasSim.push({
  id: "remota-1", tipo: "correccion", clave: EV.k,
  campos: { EVALUACION: "Corregida por otra persona" },
  previo: { EVALUACION: EV.e }, autor: "María",
  creado: "2026-10-07T12:00:00+00:00",
});
await globalThis.window.__calendario.recargar();

const cEvB = porId.rejilla.children.find((c) => c.dataset.fecha === FECHA_EV);
cEvB.click();
const itemCorr = itemDe(porId.detalle, EV.a);
if (!itemCorr) fallo("no aparece " + EV.a + " el " + FECHA_EV);
if (!itemCorr.children[1].textContent.includes("Corregida por otra persona"))
  fallo("corrección no aplicada: " + itemCorr.children[1].textContent);
const barra = barraDe(itemCorr);
const chip = barra && barra.children.find((c) => c.className === "corregido");
if (!chip || !chip.textContent.includes("María"))
  fallo("chip de autor: " + (chip ? chip.textContent : "(no está)"));
ok("corrección remota aplicada y firmada por " + chip.textContent.replace("✎ ", ""));

const btnDeshacer = barra.children.find((c) => (c.textContent || "").includes("deshacer"));
if (!btnDeshacer) fallo("falta el botón de deshacer");
btnDeshacer.click();
await tick();

const anula = posts[posts.length - 1];
if (anula.tipo !== "anula" || anula.anula !== "remota-1")
  fallo("lo enviado para deshacer: " + JSON.stringify(anula));
const cEvC = porId.rejilla.children.find((c) => c.dataset.fecha === FECHA_EV);
cEvC.click();
const itemCorrB = itemDe(porId.detalle, EV.a);
if (!itemCorrB) fallo("desapareció el evento al deshacer");
if (itemCorrB.children[1].textContent.includes("Corregida"))
  fallo("no se deshizo: " + itemCorrB.children[1].textContent);
if (barraDe(itemCorrB) &&
    barraDe(itemCorrB).children.some((c) => c.className === "corregido"))
  fallo("sigue el chip de «corregido»");
ok("deshacer: se envía «anula» y el dato vuelve a ser el original");

// 10) PWA: manifest, service worker, iconos y los botones de instalar/avisos
if (!/<link rel="manifest" href="manifest\.webmanifest">/.test(html))
  fallo("falta <link rel=\"manifest\">");
if (!/<meta name="theme-color" content="#2563eb">/.test(html))
  fallo("falta theme-color");
if (!/<link rel="apple-touch-icon" href="apple-touch-icon\.png">/.test(html))
  fallo("falta apple-touch-icon");

const man = JSON.parse(readFileSync("salida/manifest.webmanifest", "utf8"));
if (man.display !== "standalone" || man.start_url !== "./" || man.icons.length !== 3)
  fallo("manifest incompleto: " + JSON.stringify(man).slice(0, 160));
const sw = readFileSync("salida/sw.js", "utf8");
for (const gancho of ["addEventListener('push'",
                      "addEventListener('notificationclick'",
                      "addEventListener('fetch'"])
  if (!sw.includes(gancho)) fallo("sw.js sin " + gancho);
for (const icono of ["icon-192.png", "icon-512.png", "icon-maskable-512.png",
                     "apple-touch-icon.png"])
  if (readFileSync("salida/" + icono).length < 500) fallo("icono vacío: " + icono);
ok("pwa: manifest + sw.js (push/fetch) + 4 iconos");

const cfgNube = JSON.parse(porId.nube.textContent);
if (!cfgNube.vapid) fallo("la nube no trae la llave vapid de los avisos");
ok("nube con vapid: " + cfgNube.vapid.slice(0, 20) + "…");

// la app recuerda el estado: al abrir restaura la suscripción existente
if (!/function restaurarAvisos\(\)/.test(html) || !/restaurarAvisos\(\);/.test(html))
  fallo("la app no restaura el estado de los avisos al abrir");
ok("avisos: estado restaurado al abrir la app");

// sin Notification el botón de avisos queda oculto y explica el motivo
if (!porId.avisos.hidden) fallo("«Avisos» debería estar oculto sin Notification");
porId.avisos.click();
if (!porId["avisos-estado"].textContent.includes("no admite"))
  fallo("avisos sin explicación: " + JSON.stringify(porId["avisos-estado"].textContent));
ok("avisos: " + porId["avisos-estado"].textContent);

// «Probar aviso» está escondido a propósito: existe, pero jamás se muestra
if (!/id="probar"[^>]*\shidden/.test(html))
  fallo("«Probar aviso» debería llevar el atributo hidden en el HTML");
if (/btnProbar\.hidden\s*=\s*!window\.Notification/.test(html))
  fallo("«Probar aviso» no debe volver a desocultarse solo");
porId.probar.click();
if (!porId["avisos-estado"].textContent.includes("no admite"))
  fallo("probar sin explicación: " + JSON.stringify(porId["avisos-estado"].textContent));
ok("probar aviso: " + porId["avisos-estado"].textContent);

// cada prueba cierra la anterior: si no, el tag la reemplaza en silencio
if (!/getNotifications\(\{ tag: 'prueba-aviso' \}\)/.test(html)
    || !/\.close\(\)/.test(html))
  fallo("«Probar aviso» debe cerrar la prueba anterior para que reaparezca");
ok("probar aviso: cierra la anterior y lanza una fresca");

// «Instalar app» sin beforeinstallprompt da instrucciones (y no revienta)
porId.instalar.click();
if (!porId["avisos-estado"].textContent.includes("Instalar"))
  fallo("instalar sin instrucción: " + JSON.stringify(porId["avisos-estado"].textContent));
ok("instalar: " + porId["avisos-estado"].textContent);

// ---- pestañas: calendario y mensajes de la Scuola ----
const todoTexto = (el) => (el.textContent || "")
  + (el.children || []).map(todoTexto).join(" ");

globalThis.window.__calendario.mensajes([
  { id: "x1", asunto: "Excursión a Villa Grimaldi", fecha: "2026-10-13T09:15:00Z",
    puntos: ["Salida el viernes 23 a las 08:45."], accion: "Autorizar con firma.",
    eventos: [{ titulo: "Excursión", fecha_inicio: "2026-10-23T08:45:00" }] },
  { id: "x2", asunto: "Informe de notas", fecha: "2026-10-09T12:05:00Z",
    puntos: ["Se entrega el lunes 26."], accion: "", eventos: [] },
]);
if (porId["tab-mensajes"].hidden) fallo("con mensajes la pestaña debe aparecer");
if (porId["cuenta-mensajes"].textContent !== "2")
  fallo("cuenta de mensajes: " + porId["cuenta-mensajes"].textContent);
if (porId["vista-calendario"].hidden)
  fallo("el calendario debería seguir visible al cargar");
if (!porId["mensajes"].hidden)
  fallo("los mensajes deben esperar a que se abra su pestaña");
ok("pestañas: aparece «Mensajes» con " + porId["cuenta-mensajes"].textContent);

porId["tab-mensajes"].click();
if (!porId["vista-calendario"].hidden) fallo("abrir mensajes no oculta el calendario");
if (porId["mensajes"].hidden) fallo("la pestaña no mostró la sección de mensajes");
if (porId["tab-mensajes"].className !== "activa") fallo("no marcó la pestaña activa");
const items = porId["mensajes-lista"].children;
if (items.length !== 2) fallo("mensajes pintados: " + items.length);
const txt = items.map(todoTexto).join(" ");
if (!txt.includes("Excursión a Villa Grimaldi") || !txt.includes("Informe de notas"))
  fallo("faltan asuntos: " + txt);
if (!txt.includes("Autorizar con firma.") || !txt.includes("2026-10-23"))
  fallo("falta la acción o el evento: " + txt);
ok("pestaña de mensajes: 2 comunicados con asunto, puntos, acción y evento");

porId["tab-calendario"].click();
if (porId["vista-calendario"].hidden) fallo("volver al calendario no lo restauró");
if (!porId["mensajes"].hidden) fallo("volver al calendario no cerró los mensajes");
if (porId["tab-calendario"].className !== "activa") fallo("no volvió la pestaña activa");
ok("pestañas: se puede volver al calendario");
porId["tab-mensajes"].click();
if (porId["mensajes"].hidden || !porId["vista-calendario"].hidden)
  fallo("la pestaña de mensajes debe poder abrirse otra vez");
porId["tab-calendario"].click();
ok("pestañas: abrir y volver repetidamente no pierde los mensajes");

globalThis.window.__calendario.mensajes([
  { id: 'viejo', asunto: 'No mostrar agosto', fecha: '2026-09-01T03:59:59.999Z' },
  { id: 'inicio', asunto: 'Inicio de septiembre', fecha: '2026-09-01T04:00:00Z' },
  { id: 'invalido', asunto: 'Sin fecha válida', fecha: 'fecha inválida' },
  { id: 'futuro', asunto: 'No mostrar fechas futuras', fecha: '2999-10-01T12:00:00Z' },
]);
if (porId['cuenta-mensajes'].textContent !== '1')
  fallo('el filtro debe empezar el 1 de septiembre a medianoche de Chile y terminar en el presente');
if (!todoTexto(porId['mensajes-lista']).includes('Inicio de septiembre')
    || todoTexto(porId['mensajes-lista']).includes('No mostrar agosto')
    || todoTexto(porId['mensajes-lista']).includes('No mostrar fechas futuras'))
  fallo('se mostraron comunicados anteriores al inicio');
globalThis.window.__calendario.mensajes([
  { id: 'viejo', asunto: 'Agosto', fecha: '2026-08-31T15:00:00Z' },
]);
if (porId['mensajes-lista'].children.length || !porId['tab-mensajes'].hidden
    || !porId['mensajes'].hidden || porId['vista-calendario'].hidden)
  fallo('sin mensajes desde septiembre debe limpiar lo anterior y volver al calendario');
ok('mensajes: desde el 01/09/2026 inclusive en Chile hasta hoy, sin agosto ni fechas futuras/inválidas');

// Más de 20 y de 500 comunicados: todo el período, sin truncamiento silencioso.
comunicadosSim.splice(0, comunicadosSim.length, ...Array.from({ length: 501 }, (_, i) => ({
  id: 'paginado-' + i, asunto: 'Aviso ' + i, fecha: '2026-09-10T12:00:00Z', puntos: []
})));
consultasMensajes.length = 0;
await window.__calendario.recargarMensajes();
if (porId['cuenta-mensajes'].textContent !== '501' || porId['mensajes-lista'].children.length !== 501)
  fallo('no se cargó el período completo de comunicados');
if (consultasMensajes.map(q => q.get('offset')).join(',') !== '0,500')
  fallo('paginación de mensajes incorrecta');
if (!consultasMensajes.every(q => q.get('order') === 'fecha.desc,id.desc'
    && q.getAll('fecha')[0] === 'gte.2026-09-01T04:00:00.000Z'
    && q.getAll('fecha')[1].startsWith('lte.')))
  fallo('la paginación perdió el orden o los límites de fecha');
errorMensajes = true;
await window.__calendario.recargarMensajes();
if (porId['mensajes-lista'].children.length !== 501)
  fallo('un error de red borró los mensajes que ya se habían cargado');
ok('mensajes: período completo paginado (501), orden estable y sin borrar la vista ante fallos de red');

console.log("\nTODO OK");
