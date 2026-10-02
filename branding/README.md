# Marca del cliente (`branding/`)

Esta carpeta guarda los logos que muestra el kiosco. Está versionada y es
compartida por todos los sitios que usen este repositorio; **cuál logo usa cada
Pi lo decide su `.env`**, no la carpeta.

## Cómo se configura

En el `.env` del Pi (ver el paso 9 de la guía de instalación del
[README principal](../README.md)):

```
BRAND_LOGO=branding/logo_a.png
BRAND_LOGO_DARK=branding/logo_b.png
BRAND_COLOR=#111827
BRAND_FOOTER=soporte@cliente.com
```

Después de cambiar el `.env`, reiniciar el servidor:

```bash
pkill -f "venv/bin/python server.py"
```

- `BRAND_LOGO` — logo para **modo claro** (fondo claro, así que el logo debe ser
  oscuro).
- `BRAND_LOGO_DARK` — logo para **modo oscuro** (logo claro). Es opcional: si se
  deja vacío, el modo oscuro reutiliza `BRAND_LOGO`. El kiosco cambia de logo al
  instante cuando se toca el botón de tema.
- `BRAND_COLOR` — color del botón principal de la pantalla de inicio.
- `BRAND_FOOTER` — línea de texto al pie (contacto, "powered by"...).
- `BRAND_NAME` — opcional; solo se usa como texto alternativo del logo
  (accesibilidad), no se muestra en pantalla. Por eso el logo debe incluir el
  nombre del cliente si se quiere mostrar uno: no hay una etiqueta de texto
  aparte.

Con todo vacío, el kiosco usa el look por defecto: sin encabezado de logo, botón
azul y sin pie de página.

## Archivos del logo

- Formato **PNG con fondo transparente**.
- Se muestra a unos **110 px de alto** y hasta **440 px de ancho** (se ajusta
  sin deformarse). Conviene un archivo de al menos el doble de ese tamaño para
  que se vea nítido en pantallas de alta densidad; los actuales miden unos
  2700 px de ancho y pesan ≈55 KB.
- Los nombres de archivo son sensibles a mayúsculas en el Pi (Linux), aunque en
  Windows no lo sean: `Logo_A.png` y `logo_a.png` son archivos distintos allá.
- Para **no pisar el logo de otro sitio**, usar nombres distintos por cliente,
  por ejemplo `torres-del-parque_claro.png` y `torres-del-parque_oscuro.png`, y
  apuntar el `.env` de ese Pi a ellos.

## Logos actuales

`logo_a.png` y `logo_b.png` son el logo de Artcen Design (modo claro y oscuro)
del kiosco instalado actualmente.
