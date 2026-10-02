// Este archivo contiene toda la lógica y las pantallas para el administrador.
// La verificación de contraseña, la generación de códigos de recogida y las
// aperturas de casillero ahora las decide siempre el servidor — este archivo
// solo pide acciones y refleja lo que el servidor confirma.
import { showModal, closeModal } from './modal.js';
import { bays, refreshState } from '../utils/state.js';
import { exportToCSV } from '../utils/csv.js';
import { waitForDoorClose } from '../utils/hardware.js';
import { API_BASE } from '../utils/config.js';

export function showAdminLogin() {
    const content = `
        <p class="mb-4 text-gray-600 dark:text-gray-400">Por favor, introduce la contraseña de administrador para continuar.</p>
        <input type="password" id="admin-password" class="w-full p-3 border border-gray-300 dark:border-gray-600 bg-white dark:bg-gray-700 text-gray-900 dark:text-gray-100 rounded-lg mb-4" placeholder="Contraseña" inputmode="text">
        <button id="admin-submit" class="w-full bg-green-600 text-white p-3 rounded-lg hover:bg-green-700 transition mb-4">Iniciar Sesión</button>
    `;
    showModal('Login de Admin', content, 0, '#admin-password');
    document.getElementById('admin-password').focus();
    document.getElementById('admin-submit').addEventListener('click', verifyAdminPassword);
    document.getElementById('admin-password').addEventListener('keydown', (e) => {
        if (e.key === 'Enter') verifyAdminPassword();
    });
}

async function verifyAdminPassword() {
    const password = document.getElementById('admin-password').value;
    try {
        const response = await fetch(`${API_BASE}/api/admin/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ password }),
        });
        const result = await response.json();
        if (response.ok && result.success) {
            await showAdminPanel();
        } else {
            showModal('Error', '<p class="text-red-500">Contraseña incorrecta. Por favor, inténtalo de nuevo.</p>', 3000);
        }
    } catch (e) {
        console.error('Falló el login de admin:', e);
        showModal('Error de Conexión', '<p class="text-red-500">No se pudo contactar al servidor.</p>', 3000);
    }
}

/**
 * Muestra el panel de control del administrador.
 */
export async function showAdminPanel() {
    await refreshState(); // Trae el estado más reciente (incluye códigos, porque ya hay sesión de admin)

    const content = `
        <div class="mb-6">
            <h3 class="text-xl font-semibold mb-4 text-gray-700 dark:text-gray-200">Estado de los Casilleros</h3>
            <div id="admin-bays-container" class="bay-grid"></div>
        </div>
        <div class="grid grid-cols-2 gap-4 mb-6">
            <button id="deposit-package-btn" class="bg-indigo-600 text-white p-3 rounded-lg hover:bg-indigo-700 transition">Depositar Paquete</button>
            <button id="manage-bays-btn" class="bg-gray-600 text-white p-3 rounded-lg hover:bg-gray-700 transition">Gestionar Casilleros</button>
        </div>
        <div class="grid grid-cols-2 gap-4">
            <button id="export-csv-btn" class="bg-green-600 text-white p-3 rounded-lg hover:bg-green-700 transition">Exportar Reporte CSV</button>
            <button id="admin-logout-btn" class="bg-red-600 text-white p-3 rounded-lg hover:bg-red-700 transition">Cerrar Sesión</button>
        </div>
    `;
    showModal('Panel de Administrador', content);
    renderAdminBays();

    document.getElementById('deposit-package-btn').addEventListener('click', showDepositScreen);
    document.getElementById('manage-bays-btn').addEventListener('click', showManageBaysScreen);
    document.getElementById('export-csv-btn').addEventListener('click', exportToCSV);
    document.getElementById('admin-logout-btn').addEventListener('click', handleLogout);
}

async function handleLogout() {
    try {
        await fetch(`${API_BASE}/api/admin/logout`, { method: 'POST' });
    } catch (e) {
        console.error('Falló al cerrar sesión:', e);
    }
    closeModal();
}

function renderAdminBays() {
    const baysContainer = document.getElementById('admin-bays-container');
    if (!baysContainer) return;

    baysContainer.innerHTML = bays.map(bay => {
        let statusText, statusColor, details = '';

        if (bay.hardwareStatus === "DISABLED") {
            statusText = "Fuera de Servicio";
            statusColor = "gray";
            details = `<p class="text-sm text-gray-500 dark:text-gray-400">(No disponible)</p>`;
        } else if (bay.hardwareStatus === "UNLOCKED") {
            statusText = "PUERTA ABIERTA";
            statusColor = "yellow";
        } else if (bay.hardwareStatus === "UNKNOWN") {
            statusText = "DESCONOCIDO";
            statusColor = "gray";
        } else if (bay.occupied) {
            statusText = "Ocupado";
            statusColor = "red";
            details = `
                <p class="text-sm text-gray-600 dark:text-gray-300 font-medium">Para: <span class="font-normal break-all">${bay.customerEmail}</span></p>
                <p class="text-sm text-gray-600 dark:text-gray-300 font-medium mt-1">Código: <span class="font-mono text-blue-600 bg-blue-100 dark:text-blue-300 dark:bg-blue-900/50 px-2 py-1 rounded">${bay.pickupCode}</span></p>
            `;
        } else {
            statusText = "Disponible";
            statusColor = "green";
            details = `<p class="text-sm text-gray-500 dark:text-gray-400">(Cerrado y listo)</p>`;
        }

        const statusColors = {
            red: "text-red-600 bg-red-100 dark:text-red-300 dark:bg-red-900/50",
            green: "text-green-600 bg-green-100 dark:text-green-300 dark:bg-green-900/50",
            yellow: "text-yellow-600 bg-yellow-100 dark:text-yellow-300 dark:bg-yellow-900/50",
            gray: "text-gray-600 bg-gray-100 dark:text-gray-300 dark:bg-gray-900/50"
        };

        return `
            <div class="border dark:border-gray-700 rounded-xl p-4 bg-white dark:bg-gray-700 shadow-sm">
                <div class="flex justify-between items-center mb-2">
                    <h3 class="text-lg font-bold text-gray-800 dark:text-gray-100">Casillero ${bay.id}</h3>
                    <span class="text-sm font-semibold ${statusColors[statusColor]} px-3 py-1 rounded-full">${statusText}</span>
                </div>
                <div class="min-h-[40px]">${details}</div>
            </div>
        `;
    }).join('');
}

/**
 * Solo muestra casilleros disponibles (cerrados y no ocupados).
 */
function showDepositScreen() {
    const availableBays = bays.filter(bay =>
        bay.hardwareStatus === "LOCKED" && !bay.occupied
    );

    if (availableBays.length === 0) {
        showModal('No hay Casilleros Disponibles', '<p class="dark:text-gray-300">Todos los casilleros están ocupados o tienen la puerta abierta.</p>', 3000);
        return;
    }

    const bayOptions = availableBays.map(bay => `<option value="${bay.id}">Casillero ${bay.id}</option>`).join('');
    const content = `
        <p class="mb-4 text-gray-600 dark:text-gray-400">Selecciona un casillero disponible (cerrado y vacío) e introduce el correo del cliente.</p>
        <select id="bay-select" class="w-full p-3 border rounded-lg mb-4">${bayOptions}</select>
        <input type="email" id="customer-email" class="w-full p-3 border rounded-lg mb-4" placeholder="cliente@example.com" inputmode="email">
        <button id="submit-deposit" class="w-full bg-blue-600 text-white p-3 rounded-lg mb-4">Depositar y Enviar Código</button>
    `;
    showModal('Depositar Paquete', content, 0, '#customer-email');
    document.getElementById('customer-email').focus();
    document.getElementById('submit-deposit').addEventListener('click', handleDeposit);
}

async function handleDeposit() {
    const selectedBayId = parseInt(document.getElementById('bay-select').value);
    const email = document.getElementById('customer-email').value;

    if (!email || !/^\S+@\S+\.\S+$/.test(email)) {
        showModal('Correo Inválido', '<p class="text-red-500">Por favor, introduce una dirección de correo válida.</p>', 3000);
        return;
    }

    showModal('Abriendo Casillero...', `<p class="dark:text-gray-300">Enviando comando para abrir el Casillero ${selectedBayId}...</p>`, 0);

    let pickupCode;
    try {
        const response = await fetch(`${API_BASE}/api/admin/deposit`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bayId: selectedBayId, email }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || 'Fallo en la comunicación');
        pickupCode = result.pickupCode;
    } catch (error) {
        console.error("Failed to open locker:", error);
        showModal('Error de Hardware', `<p class="text-red-500">${error.message || 'No se pudo abrir el casillero. Revisa la conexión.'}</p>`, 5000);
        return;
    }

    // La puerta se abrió. Espera a que el operador la cierre para confirmar el depósito.
    waitForDoorClose(selectedBayId, async () => {
        try {
            const confirmResponse = await fetch(`${API_BASE}/api/admin/deposit/confirm`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ bayId: selectedBayId }),
            });
            const confirmResult = await confirmResponse.json();
            if (!confirmResponse.ok || !confirmResult.success) {
                throw new Error(confirmResult.error || 'Fallo al confirmar el depósito');
            }
        } catch (error) {
            console.error('Falló al confirmar el depósito:', error);
            showModal('Error', `<p class="text-red-500">El casillero se cerró pero no se pudo confirmar el depósito: ${error.message}</p>`, 5000);
            return;
        }

        await refreshState();

        const emailSent = await sendPickupEmail(selectedBayId, email);
        showQRCodeModal(pickupCode, email, emailSent);
    });
}

async function sendPickupEmail(bayId, toEmail) {
    showModal("Enviando...", `<p class="dark:text-gray-300">Enviando código de recogida a ${toEmail}</p>`, 0);
    try {
        const response = await fetch(`${API_BASE}/api/admin/deposit/send-email`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bayId }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) {
            console.error('Falló al enviar el correo:', result.error);
            return false;
        }
        return true;
    } catch (error) {
        console.error('Falló al enviar el correo:', error);
        return false;
    }
}

function showQRCodeModal(pickupCode, email, isConfirmation = false) {
    const title = isConfirmation ? 'Confirmación de Depósito' : 'Código de Recogida de Respaldo';
    const message = isConfirmation
        ? `Los siguientes detalles de recogida se enviaron con éxito a ${email}.`
        : 'Como el correo no pudo ser enviado, por favor muestra este código QR al cliente o proporciónale el código manual.';

    const content = `
        <p class="mb-4 text-center dark:text-gray-300">${message}</p>
        <div class="flex justify-center mb-4 bg-white p-2 rounded-lg"><canvas id="qr-canvas"></canvas></div>
        <p class="text-center text-2xl font-mono bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-gray-100 p-2 rounded">${pickupCode}</p>
        <p class="text-center text-sm text-gray-500 dark:text-gray-400 mt-2">Para: ${email}</p>
         <button id="qr-close-btn" class="w-full mt-4 bg-gray-500 text-white p-2 rounded-lg">Cerrar y Ver Panel</button>
    `;
    showModal(title, content);
    new QRious({ element: document.getElementById('qr-canvas'), value: pickupCode, size: 200 });

    document.getElementById('qr-close-btn').addEventListener('click', () => {
        closeModal();
        showAdminPanel();
    });
}

function showManageBaysScreen() {
    const baysContent = bays.map(bay => {
        let statusText, statusColor;
        if (bay.hardwareStatus === "DISABLED") {
            statusText = "Fuera de Servicio";
            statusColor = "text-gray-600 bg-gray-100";
        } else if (bay.hardwareStatus === "UNLOCKED") {
            statusText = "PUERTA ABIERTA";
            statusColor = "text-yellow-600 bg-yellow-100";
        } else if (bay.hardwareStatus === "LOCKED") {
            statusText = bay.occupied ? "Ocupado" : "Disponible (Cerrado)";
            statusColor = bay.occupied ? "text-red-600 bg-red-100" : "text-green-600 bg-green-100";
        } else {
            statusText = "Desconocido";
            statusColor = "text-gray-600 bg-gray-100";
        }

        const isDisabled = bay.hardwareStatus === "DISABLED";
        return `
        <div class="border dark:border-gray-600 rounded-lg p-4 flex flex-col justify-between">
            <div class="flex justify-between items-center mb-3">
               <h4 class="font-bold dark:text-gray-100">Casillero ${bay.id}</h4>
               <span class="text-xs font-semibold ${statusColor} px-2 py-1 rounded-full">${statusText}</span>
            </div>
            ${isDisabled ? '' : `
            <div class="flex space-x-2">
               <button data-bay-id="${bay.id}" class="open-door-btn flex-1 bg-yellow-500 text-black p-2 rounded-lg text-sm">Abrir Puerta</button>
               ${bay.occupied ? `<button data-bay-id="${bay.id}" class="clear-bay-btn flex-1 bg-red-600 text-white p-2 rounded-lg text-sm">Liberar</button>` : ''}
            </div>
            `}
        </div>
    `}).join('');

    const content = `
        <p class="mb-4 text-gray-600 dark:text-gray-400">Abre manualmente un casillero para mantenimiento o libera un casillero ocupado.</p>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">${baysContent}</div>
    `;
    showModal('Gestionar Casilleros', content);

    document.querySelectorAll('.open-door-btn').forEach(button => {
        button.addEventListener('click', async (e) => {
            const bayId = e.currentTarget.dataset.bayId;
            showModal('Abriendo...', `<p>Enviando comando para abrir el Casillero ${bayId}...</p>`, 0);

            try {
                const response = await fetch(`${API_BASE}/api/admin/open`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ bayId }),
                });
                const result = await response.json();
                if (!response.ok || !result.success) throw new Error(result.error || 'Fallo al abrir');

                showModal('Éxito', `<p>Casillero ${bayId} ha sido abierto.</p>`, 2000);
                await refreshState();
                setTimeout(showManageBaysScreen, 2000);
            } catch (error) {
                console.error("Failed to open locker:", error);
                showModal('Error', `<p class="text-red-500">No se pudo abrir el casillero: ${error.message}</p>`, 4000);
            }
        });
    });

    document.querySelectorAll('.clear-bay-btn').forEach(button => {
        button.addEventListener('click', (e) => confirmClearBay(parseInt(e.currentTarget.dataset.bayId)));
    });
}

function confirmClearBay(bayId) {
    const content = `
        <p class="mb-4 text-gray-700 dark:text-gray-300">¿Seguro que quieres liberar el Casillero ${bayId}? Esto lo marcará como disponible y borrará su código. Esta acción no se puede deshacer.</p>
        <div class="flex justify-end space-x-3">
            <button id="cancel-clear-btn" class="bg-gray-200 px-4 py-2 rounded-lg">Cancelar</button>
            <button id="confirm-clear-btn" class="bg-red-600 text-white px-4 py-2 rounded-lg">Sí, Liberar</button>
        </div>
    `;
    showModal(`Confirmar Liberación Casillero ${bayId}`, content);

    document.getElementById('cancel-clear-btn').addEventListener('click', showManageBaysScreen);
    document.getElementById('confirm-clear-btn').addEventListener('click', () => handleClearBay(bayId));
}

async function handleClearBay(bayId) {
    try {
        const response = await fetch(`${API_BASE}/api/admin/clear`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ bayId }),
        });
        const result = await response.json();
        if (!response.ok || !result.success) throw new Error(result.error || 'Fallo al liberar el casillero');
    } catch (error) {
        console.error('Falló al liberar el casillero:', error);
        showModal('Error', `<p class="text-red-500">${error.message}</p>`, 4000);
    }
    await refreshState();
    showManageBaysScreen();
}
