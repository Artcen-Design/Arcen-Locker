// Configuración compartida de la aplicación. Único lugar para valores que
// dependen del sitio (como el número de casilleros o la marca del cliente).

// El frontend es servido por el propio server.py, así que las llamadas a la
// API son del mismo origen — no hace falta una URL absoluta.
export const API_BASE = '';

// Valores por defecto hasta que se confirmen con el servidor.
export let NUM_LOCKERS = 8;
export let BRAND_NAME = '';
export let BRAND_LOGO = '';
export let BRAND_LOGO_DARK = '';
export let BRAND_COLOR = '#2563eb';
export let BRAND_FOOTER = '';

/**
 * Carga la configuración específica del sitio (número de casilleros, marca
 * del cliente) desde el servidor, para no tener que hardcodearla.
 */
export async function loadRemoteConfig() {
    try {
        const response = await fetch(`${API_BASE}/api/config`);
        if (!response.ok) return;
        const data = await response.json();
        if (data.numLockers) NUM_LOCKERS = data.numLockers;
        if (data.brandName) BRAND_NAME = data.brandName;
        if (data.brandLogo) BRAND_LOGO = data.brandLogo;
        if (data.brandLogoDark) BRAND_LOGO_DARK = data.brandLogoDark;
        if (data.brandColor) BRAND_COLOR = data.brandColor;
        if (data.brandFooter) BRAND_FOOTER = data.brandFooter;
    } catch (e) {
        console.error('No se pudo cargar la configuración del servidor, usando valores por defecto.', e);
    }
}
