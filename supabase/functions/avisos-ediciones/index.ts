import { createClient } from 'npm:@supabase/supabase-js@2.106.1';
import webpush from 'npm:web-push@3.6.7';
import { crearHandler, procesarTrabajo } from './core.mjs';

function requerido(nombre: string): string {
  const valor = Deno.env.get(nombre)?.trim();
  if (!valor) throw new Error('Falta configurar ' + nombre);
  return valor;
}

// Sólo existen en el servidor. Ninguna de estas claves se incrusta en la web.
const supabase = createClient(requerido('SUPABASE_URL'),
  requerido('SUPABASE_SERVICE_ROLE_KEY'), { auth: { persistSession: false } });
const pagina = requerido('PUSH_SITE_URL');
const destino = new URL(pagina);
if (destino.protocol !== 'https:') throw new Error('PUSH_SITE_URL debe ser https');
webpush.setVapidDetails(requerido('VAPID_SUBJECT'), requerido('VAPID_PUBLIC_KEY'),
  requerido('VAPID_PRIVATE_KEY'));

async function rpc(nombre: string, parametros = {}) {
  const { data, error } = await supabase.rpc(nombre, parametros);
  if (error) throw new Error('Falló la operación de la cola');
  return data;
}

Deno.serve(crearHandler({
  secreto: requerido('PUSH_WEBHOOK_SECRET'),
  tomar: () => rpc('push_ediciones_tomar'),
  procesar: (trabajo: any) => procesarTrabajo(trabajo, {
    pagina,
    enviar: (s: any, mensaje: any) => webpush.sendNotification({
      endpoint: s.endpoint, keys: { p256dh: s.p256dh, auth: s.auth },
    }, JSON.stringify(mensaje), { TTL: 86400, urgency: 'high', timeout: 5000 }),
    resultado: (id: string, lease: string, endpoint: string, estado: string) =>
      rpc('push_ediciones_resultado', {
        p_id: id, p_lease: lease, p_endpoint: endpoint, p_estado: estado,
      }),
  }),
  soltar: (id: string, lease: string) => rpc('push_ediciones_soltar', { p_id: id, p_lease: lease }),
  despertar: () => rpc('push_ediciones_despertar'),
}));
