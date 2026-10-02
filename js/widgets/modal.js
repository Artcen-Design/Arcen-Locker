// Un widget reutilizable para mostrar y ocultar modales.
const modalContainer = document.getElementById('modal-container');
let keyboard; // Mantener una referencia a la instancia del teclado
let capsLock = false;

/**
 * Muestra un modal con un título y contenido específico.
 * @param {string} title - El título del modal.
 * @param {string} content - El contenido HTML del modal.
 * @param {number} [autoCloseDelay=0] - Tiempo en ms para autocerrar. 0 para no autocerrar.
 * @param {string|null} [inputSelector=null] - El selector para el input al que adjuntar el teclado.
 */
export function showModal(title, content, autoCloseDelay = 0, inputSelector = null) {
    closeModal(); // Cierra cualquier modal existente primero
    const modalBackdrop = document.createElement('div');
    modalBackdrop.className = 'modal-backdrop';
    modalBackdrop.id = 'modal-backdrop';

    if (inputSelector) {
        content += '<div class="simple-keyboard"></div>';
    }

    const modalContent = document.createElement('div');
    modalContent.className = 'modal-content';
    modalContent.innerHTML = `
        <h2 class="text-2xl font-bold mb-4 text-gray-800 dark:text-gray-100">${title}</h2>
        <div id="modal-body">${content}</div>
    `;

    modalBackdrop.appendChild(modalContent);
    modalContainer.appendChild(modalBackdrop);

    // Activa la animación
    setTimeout(() => modalBackdrop.classList.add('active'), 10);

    if (inputSelector) {
        const Keyboard = window.SimpleKeyboard.default;

        keyboard = new Keyboard({
            onChange: input => {
                document.querySelector(inputSelector).value = input;
            },
            onKeyPress: button => {
                if (button === "{lock}") handleShift();
            },
            layout: {
                'default': [
                    '` 1 2 3 4 5 6 7 8 9 0 - = {bksp}',
                    '{tab} q w e r t y u i o p [ ] \\',
                    '{lock} a s d f g h j k l ; \' {enter}',
                    '{shift} z x c v b n m , . / {shift}',
                    '.com @ {space}'
                ],
                'shift': [
                    '~ ! @ # $ % ^ & * ( ) _ + {bksp}',
                    '{tab} Q W E R T Y U I O P { } |',
                    '{lock} A S D F G H J K L : " {enter}',
                    '{shift} Z X C V B N M < > ? {shift}',
                    '.com @ {space}'
                ]
            },
            display: {
                '{lock}': 'Caps',
                '{bksp}': 'Borrar',
                '{enter}': 'Enter',
                '{shift}': 'Shift',
                '{space}': 'Espacio',
                '{tab}': 'Tab'
            },
            theme: `hg-theme-default`,
        });

        document.querySelector(inputSelector).addEventListener('input', event => {
            keyboard.setInput(event.target.value);
        });
    }

    if (autoCloseDelay > 0) {
        setTimeout(closeModal, autoCloseDelay);
    }

    modalBackdrop.addEventListener('click', (e) => {
        if (e.target === modalBackdrop) closeModal();
    });
}

/**
 * Cierra el modal activo.
 */
// CÓDIGO NUEVO (CORREGIDO)
export function closeModal() {
    if (keyboard) {
        keyboard.destroy();
        keyboard = null;
        capsLock = false;
    }
    const modalBackdrop = document.getElementById('modal-backdrop');
    if (modalBackdrop) {
        modalBackdrop.remove();
    }
}

function handleShift() {
    capsLock = !capsLock;
    keyboard.setOptions({
        layoutName: capsLock ? "shift" : "default"
    });
}