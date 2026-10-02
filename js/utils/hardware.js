// Este archivo contiene lógica para interactuar con el hardware,
// como esperar a que se cierre una puerta.
import { showModal, closeModal } from '../widgets/modal.js';
import { API_BASE } from './config.js';

/**
 * Muestra un modal y sondea el estado de un casillero hasta que se cierra.
 * @param {number} bayId - El ID del casillero que se está sondeando.
 * @param {function} onClosedCallback - La función a llamar cuando se confirma el cierre.
 */
export function waitForDoorClose(bayId, onClosedCallback) {
    
    // 1. Informa al usuario que debe cerrar la puerta
    showModal(
        `Por favor, cierre la puerta del Casillero ${bayId}`,
        `<p class="text-lg text-center dark:text-gray-300">
            El sistema está esperando a que la puerta se cierre de forma segura.
        </p>
        <div class="w-full flex justify-center py-4">
            <i class="fas fa-door-closed fa-3x fa-spin dark:text-gray-400"></i>
        </div>
        <p class="text-center text-sm text-gray-500 dark:text-gray-400">
            (Esto se detectará automáticamente)
        </p>`,
        0 // No autocerrar
    );

    // 2. Inicia el sondeo (polling)
    const poller = setInterval(async () => {
        try {
            const response = await fetch(`${API_BASE}/api/lockers/${bayId}/status`);
            if (!response.ok) {
                console.error("Error de red al sondear el casillero.");
                return; // Intenta de nuevo en el próximo intervalo
            }
            
            const data = await response.json();
            
            if (data.success && data.status === "LOCKED") {
                // 3. ¡Éxito! La puerta está cerrada.
                console.log(`Casillero ${bayId} confirmado como CERRADO.`);
                clearInterval(poller); // Detiene el sondeo
                closeModal(); // Cierra el modal de "espere"
                onClosedCallback(); // Ejecuta la acción final (marcar como disponible)
            }
            // Si es "UNLOCKED", no hace nada y espera al próximo sondeo
            
        } catch (e) {
            console.error(`Fallo en el sondeo del casillero ${bayId}:`, e);
            // Sigue intentando
        }
    }, 2000); // Comprueba cada 2 segundos
}