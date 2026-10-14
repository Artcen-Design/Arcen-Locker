// Detecta errores de dedo comunes en el dominio del correo (gmai.com, hotmial.com...).
// El servidor SMTP acepta cualquier dirección con forma válida y el rebote llega
// después, a la bandeja del remitente, así que la única defensa en el momento del
// depósito es avisar al operador antes de abrir el casillero.

const DOMINIOS_COMUNES = [
    'gmail.com', 'hotmail.com', 'outlook.com', 'yahoo.com', 'icloud.com',
    'live.com', 'msn.com', 'me.com', 'protonmail.com', 'aol.com',
    'hotmail.es', 'outlook.es', 'yahoo.es', 'hotmail.com.mx', 'yahoo.com.mx',
];

// Distancia de edición con transposición de letras adyacentes (gmial -> gmail = 1).
function distancia(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            const costo = a[i - 1] === b[j - 1] ? 0 : 1;
            d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + costo);
            if (i > 1 && j > 1 && a[i - 1] === b[j - 2] && a[i - 2] === b[j - 1]) {
                d[i][j] = Math.min(d[i][j], d[i - 2][j - 2] + 1);
            }
        }
    }
    return d[a.length][b.length];
}

/**
 * Devuelve la dirección corregida si el dominio parece un error de dedo de uno
 * común, o null si está bien o no se parece a ninguno.
 */
export function suggestEmail(email) {
    const arroba = email.lastIndexOf('@');
    if (arroba < 1) return null;
    const usuario = email.slice(0, arroba);
    const dominio = email.slice(arroba + 1).trim().toLowerCase();
    if (DOMINIOS_COMUNES.includes(dominio)) return null;
    const parecido = DOMINIOS_COMUNES.find(d => distancia(dominio, d) === 1);
    return parecido ? `${usuario}@${parecido}` : null;
}

export function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
}
