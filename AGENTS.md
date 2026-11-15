# Guía del repositorio
Paquete Python sin más dependencia que httpx. Todo cambio con prueba en `tests/` (`python -m pytest`). Las importaciones del
paquete son relativas (se copia dentro de otras aplicaciones). No incluir IPs, rutas, tokens ni datos internos.
Un cambio de comportamiento de red o de licencias debe revisarse en Commons (Rebost) y EduCrea.
