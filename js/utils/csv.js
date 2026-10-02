// Exporta un reporte de solo lectura del estado de los casilleros.
// La importación de CSV se eliminó: el servidor (SQLite) es ahora la única
// fuente de verdad del estado, así que "importar" un CSV arbitrario ya no
// tenía sentido y era una superficie de ataque innecesaria.
import { bays } from './state.js';

export function exportToCSV() {
    const headers = "id,occupied,customerEmail,pickupCode,hardwareStatus";
    const csvContent = bays.map(bay =>
        `${bay.id},${bay.occupied},${bay.customerEmail || ''},${bay.pickupCode || ''},${bay.hardwareStatus || ''}`
    ).join('\n');

    const fullCsv = `${headers}\n${csvContent}`;
    const blob = new Blob([fullCsv], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement("a");
    if (link.download !== undefined) {
        const url = URL.createObjectURL(blob);
        link.setAttribute("href", url);
        link.setAttribute("download", `locker_report_${new Date().toISOString().slice(0, 10)}.csv`);
        link.style.visibility = 'hidden';
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        URL.revokeObjectURL(url);
    }
}
