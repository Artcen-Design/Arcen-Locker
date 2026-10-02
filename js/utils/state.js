// Este archivo maneja todo lo relacionado con el estado de los casilleros.
// El servidor (server.py + SQLite) es la única fuente de verdad: aquí solo
// guardamos una copia en memoria para dibujar la UI.
import { showModal } from '../widgets/modal.js';
import { API_BASE } from './config.js';

export let bays = [];

/**
 * Carga el estado actual de los casilleros desde el servidor, que ya
 * combina la base de datos con el estado físico real del hardware.
 */
export async function initializeState() {
    try {
        await refreshState(true);
    } catch (e) {
        console.error("¡FALLO CRÍTICO! No se pudo conectar al servidor de casilleros.", e);
        bays = readSnapshot();
        showModal(
            "Error de Conexión",
            `<p class="text-red-500">No se pudo conectar al servidor. El estado mostrado puede estar desactualizado.</p>`,
            0
        );
    }
}

/**
 * Vuelve a pedir el estado más reciente al servidor. Se llama después de
 * cualquier acción de admin/cliente para que la UI refleje lo que el
 * servidor realmente aprobó, no lo que el cliente asumió.
 */
export async function refreshState(throwOnError = false) {
    try {
        const response = await fetch(`${API_BASE}/api/lockers`);
        if (!response.ok) throw new Error(`Error de red: ${response.statusText}`);

        const data = await response.json();
        if (!data.success) throw new Error('El servidor falló al obtener el estado');

        bays = data.bays;
        cacheSnapshot();
    } catch (e) {
        if (throwOnError) throw e;
        console.error("Falló al refrescar el estado", e);
    }
}

// --- Copia de respaldo NO autoritativa ---
// Solo se usa para mostrar algo razonable si el servidor no responde por un
// instante. Nunca se usa para decidir si un casillero puede abrirse: esa
// decisión la toma siempre el servidor.
function cacheSnapshot() {
    try {
        localStorage.setItem('lockerStateSnapshot', JSON.stringify(bays));
    } catch (e) {
        // No crítico si falla (p.ej. almacenamiento lleno o deshabilitado).
    }
}

function readSnapshot() {
    try {
        const saved = localStorage.getItem('lockerStateSnapshot');
        return saved ? JSON.parse(saved) : [];
    } catch (e) {
        return [];
    }
}
