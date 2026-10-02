// Este archivo maneja la interfaz y lógica para el cliente.
// La validez del código de recogida la decide siempre el servidor — este
// archivo nunca compara el código contra datos locales.
import { showModal, closeModal } from './modal.js';
import { refreshState } from '../utils/state.js';
import { waitForDoorClose } from '../utils/hardware.js';
import { API_BASE } from '../utils/config.js';

/**
 * Muestra la pantalla para que el cliente introduzca su código de recogida.
 */
export function showPickupScreen() {
    const content = `
         <p class="mb-4 text-gray-600 dark:text-gray-400">Escanea el código QR de tu correo o introduce el código manualmente.</p>
         <div id="scanner-indicator" class="scanner-placeholder">
            <i class="fas fa-qrcode fa-5x"></i>
            <p>Listo para escanear</p>
         </div>
         <input type="text" id="pickup-code-input" class="w-full p-3 text-center tracking-widest font-mono border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg mb-4" placeholder="INTRODUCE EL CÓDIGO" autocapitalize="characters" inputmode="text">
         <button id="submit-pickup-code" class="w-full bg-blue-600 text-white p-3 rounded-lg hover:bg-blue-700 transition mb-4">Enviar Código</button>
    `;
    showModal('Recoger Paquete', content, 0, '#pickup-code-input');

    const input = document.getElementById('pickup-code-input');
    input.focus();

    // El lector QR USB es un "teclado wedge": solo escribe donde haya foco.
    // Como esto es una pantalla táctil, cualquier toque fuera del teclado en
    // pantalla podría quitarle el foco al campo, así que lo recuperamos.
    const modalBody = document.getElementById('modal-body');
    modalBody.addEventListener('click', (e) => {
        if (e.target.closest('.simple-keyboard') || e.target === input) return;
        input.focus();
    });

    document.getElementById('submit-pickup-code').addEventListener('click', verifyCode);
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') verifyCode();
    });
}

/**
 * Envía el código de recogida al servidor para que lo valide y, si es
 * correcto, abra el casillero correspondiente.
 */
async function verifyCode() {
    const codeInput = document.getElementById('pickup-code-input');
    const code = codeInput.value.trim().toUpperCase();
    if (!code) return;

    try {
        const response = await fetch(`${API_BASE}/api/pickup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code }),
        });
        const result = await response.json();

        if (response.ok && result.success) {
            const bayId = result.bayId;
            showModal('¡Éxito!', `<p class="dark:text-gray-300">Casillero ${bayId} abierto.</p><p class="dark:text-gray-300">Por favor, recoge tu paquete y <strong>CIERRA LA PUERTA</strong>.</p>`, 0);

            waitForDoorClose(bayId, async () => {
                try {
                    const confirmResponse = await fetch(`${API_BASE}/api/pickup/confirm`, {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ bayId, code }),
                    });
                    const confirmResult = await confirmResponse.json();
                    if (!confirmResponse.ok || !confirmResult.success) {
                        console.error('Falló al confirmar la recogida:', confirmResult.error);
                    }
                } catch (e) {
                    console.error('Falló al confirmar la recogida:', e);
                } finally {
                    await refreshState();
                    closeModal();
                }
            });
            return;
        }

        if (response.status === 429) {
            showModal('Demasiados Intentos', `<p class="text-red-500">${result.error}</p>`, 4000);
            return;
        }

        codeInput.classList.add('border-red-500');
        showModal('Código Inválido', '<p class="text-red-500">El código que introduciste no es válido o ya ha sido usado. Por favor, inténtalo de nuevo.</p>', 4000);
        setTimeout(() => {
            if (codeInput) codeInput.classList.remove('border-red-500');
        }, 4000);
    } catch (error) {
        console.error('Failed to verify pickup code:', error);
        showModal('Error de Conexión', '<p class="text-red-500">No se pudo contactar al servidor. Por favor, contacta a soporte.</p>', 5000);
    }
}
