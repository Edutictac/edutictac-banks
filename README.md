# edutictac-banks

Motores compartidos de **bancos de recursos libres** para las aplicaciones EduTicTac (MIT). Una sola implementación, con
las defensas de red ya resueltas, usada por Commons (Rebost) y EduCrea.

| Proveedor | Contenido | Licencias admitidas |
|---|---|---|
| `arasaac` | pictogramas | CC BY-NC-SA 4.0 (se etiqueta, uso no comercial) |
| `wikimedia` | fotos e ilustraciones | libres; se descartan NC y ND |
| `met` | arte del Metropolitan | CC0 (dominio público) |
| `openverse` | imágenes | CC0, CC BY, CC BY-SA |
| `icons` | iconos y emojis (Iconify: Tabler, Lucide, Fluent Emoji, OpenMoji) | MIT, ISC, CC BY-SA |
| `openverse-audio` | sonidos (Freesound, Wikimedia) | CC0, CC BY, CC BY-SA |

```python
from edutictac_banks import Banks, BankError

banks = Banks(image_prefix="/api/image-banks")            # base de las URL de miniatura/contenido
result = banks.search("arasaac", "casa", "va")             # {provider, kind, license, items: [...]}
data, media_type = banks.image("arasaac", "2249", 300)     # miniatura (≤300) o contenido
```
Opciones de `Banks`: `sound_prefix`/`sound_suffix` (URL de los sonidos), `max_sound_bytes`, `icon_media_type`
(`image/svg+xml` por defecto; `image/png` si la aplicación rasteriza ella). Errores: `BankError(status, code)` con
códigos estables (`bank_unavailable`, `bank_timeout`, `bank_too_large`, `bank_invalid_image`, `bank_not_found`, `bank_query`…).

## Defensas
- Solo se consultan los anfitriones fijos de cada proveedor; las URL de imagen/sonido que devuelven pasan por https:443,
  direcciones públicas y redirecciones revalidadas (máx. 3). Los sonidos solo siguen `freesound.org` y `wikimedia.org`.
- **Anti DNS rebinding:** cada salto resuelve el nombre una vez, exige que todas las respuestas sean públicas y conecta
  a esa IP con `Host` y SNI del nombre (el certificado se verifica contra el nombre).
- Firma (PNG, JPEG, WebP; OGG, MP3, WAV) y tamaño comprobados. Los iconos se sirven como **SVG saneado** por lista blanca.
- Caché en memoria por instancia y limitador de ritmo opcional (`Banks.rate(owner)`).

## Uso en las aplicaciones
Se copia el directorio `edutictac_banks/` dentro de cada aplicación (`scripts/sync-banks.sh <destino>`), igual que
`@edutictac/rebost-client`. Todas las importaciones son relativas. Las pruebas de cada aplicación usan
`edutictac_banks.testing.install(monkeypatch, handler)`: sin red ni DNS reales; el `handler` ve la URL lógica.

Pruebas: `python -m pytest` (httpx y pytest).
