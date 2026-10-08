// Ejecuta el JavaScript de salida/calendario_evaluaciones.html contra un DOM
// simulado: comprueba que pinta el mes, que los clics funcionan, que el botón
// «Descargar .ics» entrega exactamente el .ics incrustado, que los resúmenes
// que calcula el JavaScript coinciden con los de Python y que el editor de la
// comunidad (nuevo evento, corrección remota y deshacer) manda lo correcto a
// Supabase.
import { readFileSync } from "node:fs";

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
                  "instalar", "avisos", "probar", "avisos-estado"]) {
  const el = new Elem("div");
  el.id = id;
  porId[id] = el;
  if (id === "datos" || id === "ics-b64" || id === "nube") {
    const mm = html.match(new RegExp(`id="${id}">([\\s\\S]*?)</script>`));
    if (!mm) throw new Error(`no encontré #${id}`);
    el.textContent = mm[1].trim();
  }
}

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
globalThis.fetch = async (url, opts = {}) => {
  if (opts && opts.method === "POST") {
    const cuerpo = JSON.parse(opts.body);
    const fila = { id: "f" + (posts.length + 1),
                   creado: new Date().toISOString(), ...cuerpo };
    filasSim.push(fila);
    posts.push(fila);
    return { ok: true, status: 201, text: async () => JSON.stringify([fila]) };
  }
  return { ok: true, status: 200,
           json: async () => [...filasSim],
           text: async () => JSON.stringify(filasSim) };
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

// 1) pintado inicial
if (porId["mes-actual"].textContent !== "Octubre 2026")
  fallo("mes inicial: " + porId["mes-actual"].textContent);
ok("mes inicial: " + porId["mes-actual"].textContent);

const celdas = porId.rejilla.children;
if (celdas.length !== 35) fallo("celdas de octubre: " + celdas.length);
ok("rejilla de octubre: 35 celdas");

const c14 = celdas.find((c) => c.dataset.fecha === "2026-10-14");
if (!c14) fallo("no está la celda del 14");
if (!c14.children.some((h) => h.className === "ev resumen" || (h.className || "").includes("ev")))
  fallo("la celda del 14 no tiene eventos");
ok("14 oct: " + c14.children.filter((h) => (h.className || "").includes("ev")).length + " chips");

// 2) clic en el sábado 10 (sólo resumen)
const c10 = celdas.find((c) => c.dataset.fecha === "2026-10-10");
if (!c10) fallo("no está la celda del sábado 10");
c10.click();
const det = porId.detalle;
if (det.children.length !== 2 || det.children[1].className !== "caja-resumen")
  fallo("detalle del 10: " + det.children.map((c) => c.className).join(","));
if (!det.children[1].children[0].textContent.includes("14, 15 y 16 oct"))
  fallo("resumen: " + det.children[1].children[0].textContent);
const pre10 = det.children[1].children[1];
const fechas10 = pre10.textContent.split("\n\n");
if (fechas10.length < 3 || fechas10.some((f) => !f.trim()))
  fallo("el resumen debe separar las fechas con línea en blanco: "
        + JSON.stringify(pre10.textContent));
ok("clic en sábado 10 -> resumen: " + det.children[1].children[0].textContent);
ok("   línea en blanco entre las 3 fechas (" + (fechas10.length - 1) + " saltos)");

// 3) clic en una fecha con evaluación
c14.click();
if (det.children.length !== 1)
  fallo("detalle del 14: " + det.children.length + " bloques");
const item = det.children[0];
if (!item.children[0].textContent.includes("IDIOMA EXTRANJERO"))
  fallo("asignatura: " + item.children[0].textContent);
if (!item.children[1].textContent.includes("SE4-1"))
  fallo("título: " + item.children[1].textContent);
if (!item.children[2].textContent.includes("Prof"))
  fallo("meta: " + item.children[2].textContent);
if (item.children[2].textContent.indexOf("\n") < 0)
  fallo("meta sin un item por linea: " + item.children[2].textContent);
ok("clic en 14 oct -> " + item.children[0].textContent + " · "
   + item.children[1].textContent + " · "
   + item.children[2].textContent.split("\n").join(" > "));

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
if (!porId.leyenda.children.length || porId.leyenda.children.length !== 10)
  fallo("leyenda: " + porId.leyenda.children.length);
ok("leyenda: 10 asignaturas");
const reglaLeyenda = (html.match(/#leyenda\s*{[^}]*}/) || [])[0] || "";
if (!/justify-content:\s*space-between/.test(reglaLeyenda))
  fallo("la leyenda debe justificarse dentro del cuadro: " + reglaLeyenda);
ok("leyenda justificada dentro del cuadro");

// 6) descarga del .ics
porId.descargar.click();
if (!descargado) fallo("no se descargó nada");
const bytes = Buffer.from(await descargado.arrayBuffer());
const b64 = porId["ics-b64"].textContent.trim();
if (bytes.toString("base64") !== b64) fallo("el .ics descargado no coincide con el incrustado");
const texto = bytes.toString("utf8");
const eventos = (texto.match(/BEGIN:VEVENT/g) || []).length;
if (eventos !== 132) fallo("eventos descargados: " + eventos);
ok("descarga .ics: " + eventos + " eventos, idéntico al incrustado");
if (!/download = 'Evaluacion Scuola\.ics'/.test(html))
  fallo("el .ics debe descargarse como «Evaluacion Scuola.ics»");
ok("nombre del archivo: Evaluacion Scuola.ics");

// 7) la nube está viva y los resúmenes del JS son los de Python
if (!porId["nube-estado"].textContent.includes("0 correcciones"))
  fallo("estado de la nube: " + porId["nube-estado"].textContent);
ok("nube conectada: " + porId["nube-estado"].textContent);

const datos = JSON.parse(porId.datos.textContent);
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
porId["m-FECHA"].value = "2026-10-21";
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
if (alta.campos.FECHA !== "2026-10-21") fallo("fecha del alta: " + alta.campos.FECHA);
if (!porId.modal.hidden) fallo("el modal no se cerró al guardar");
ok("alta enviada: " + alta.clave + " · " + alta.autor);

const c21 = porId.rejilla.children.find((c) => c.dataset.fecha === "2026-10-21");
if (!c21) fallo("no está la celda del 21");
c21.click();
const det21 = porId.detalle;
const item21 = itemDe(det21, "MATEMÁTICA");
if (!item21) fallo("el evento nuevo no aparece el 21: "
                   + det21.children.map((c) => c.className).join(","));
ok("evento nuevo visible el 21 oct (" + item21.children[1].textContent + ")");

// 9) una corrección de otra persona aparece, con su autor, y se puede deshacer
const ev14 = datos.eventos.find((e) => e.f === "2026-10-14");
if (!ev14) fallo("no encuentro el evento del 14 en los datos");
filasSim.push({
  id: "remota-1", tipo: "correccion", clave: ev14.k,
  campos: { EVALUACION: "Corregida por otra persona" },
  previo: { EVALUACION: ev14.e }, autor: "María",
  creado: "2026-10-07T12:00:00+00:00",
});
await globalThis.window.__calendario.recargar();

const c14b = porId.rejilla.children.find((c) => c.dataset.fecha === "2026-10-14");
c14b.click();
const item14 = itemDe(porId.detalle, ev14.a);
if (!item14) fallo("no aparece " + ev14.a + " el 14");
if (!item14.children[1].textContent.includes("Corregida por otra persona"))
  fallo("corrección no aplicada: " + item14.children[1].textContent);
const barra = barraDe(item14);
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
const c14c = porId.rejilla.children.find((c) => c.dataset.fecha === "2026-10-14");
c14c.click();
const item14b = itemDe(porId.detalle, ev14.a);
if (!item14b) fallo("desapareció el evento al deshacer");
if (item14b.children[1].textContent.includes("Corregida"))
  fallo("no se deshizo: " + item14b.children[1].textContent);
if (barraDe(item14b) &&
    barraDe(item14b).children.some((c) => c.className === "corregido"))
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

console.log("\nTODO OK");
