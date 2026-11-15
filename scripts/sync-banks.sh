#!/usr/bin/env bash
# Copia edutictac_banks/ al destino indicado. Uso: sync-banks.sh <directorio-destino> [ruta-al-paquete]
# El destino queda como <directorio-destino>/edutictac_banks/ (con VERSION.txt del commit de origen).
set -euo pipefail
DEST="${1:?directorio destino}"
SRC="${2:-$(cd "$(dirname "$0")/.." && pwd)/edutictac-banks}"
rm -rf "$DEST/edutictac_banks"
mkdir -p "$DEST"
cp -r "$SRC/edutictac_banks" "$DEST/edutictac_banks"
find "$DEST/edutictac_banks" -name __pycache__ -type d -prune -exec rm -rf {} +
echo "copiado de edutictac-banks $(git -C "$SRC" rev-parse --short HEAD); no editar aquí (el paquete es la fuente)" > "$DEST/edutictac_banks/VERSION.txt"
