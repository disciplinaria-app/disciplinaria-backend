# Registro de portales oficiales

Este archivo documenta cómo accede el servidor a cada portal y qué se ha comprobado en vivo. La especificación exige un reconocimiento vivo antes de dar por buenos los adaptadores; ese reconocimiento **no se ha ejecutado todavía** (el entorno de construcción no alcanzaba dominios `.gov.co`). Las filas «Comprobado en vivo» se llenan en la primera prueba real con `diagnosticar_portales` y las pruebas de aceptación del final.

| Corporación | Punto de entrada configurado | Mecanismo | Comprobado en vivo |
|---|---|---|---|
| Corte Constitucional | `https://www.corteconstitucional.gov.co/relatoria/` · patrón `/relatoria/{año}/{TIPO}-{num}-{aa}.htm` | HTTP directo por patrón; buscador HTTP y navegador como respaldo | pendiente |
| Corte Suprema de Justicia | `https://consultajurisprudencial.ramajudicial.gov.co/WebRelatoria/csj/index.xhtml` | navegador (formulario JSF) | pendiente |
| Consejo de Estado | `https://samai.consejodeestado.gov.co` | navegador (buscador dinámico) | pendiente |
| CNDJ | `https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml` | navegador (formulario JSF) | pendiente |

## Qué revisar en el reconocimiento vivo

Para cada portal, anotar aquí: `robots.txt` y términos de uso; si la búsqueda exige JavaScript; cómo se llaman los campos del formulario (para ajustar `WR_CAMPO_TEXTO`, `WR_BOTON_BUSCAR`, `WR_FILAS`, `WR_ENLACE`, `WR_SIGUIENTE`); cómo se descarga el documento (HTML o PDF); si hay paginación y cómo se avanza; límites de tasa observados.

## Pruebas de aceptación por portal (por ejecutar)

1. Cita exacta conocida → `verificar_cita` devuelve `confirmada` con URL oficial.
2. Búsqueda temática sin número → `buscar_providencia` devuelve candidatos con `coverage_status: completa`.
3. Frase de ratio → el pasaje localizado tiene `similitud` ≥ 0.6 y rol `mayoria_motiva`.
4. Actualización desde sentencia hito → `actualizar_linea` devuelve decisiones de la ventana.
5. Metadatos alterados (ponente o fecha falsos) → `discrepante`, nunca `confirmada`.
6. Ratio presente solo en salvamento → `solo_en_salvamento: true`.
7. Portal caído → `portal_no_disponible` o `timeout`, nunca `no_hallada` con texto de inexistencia.
8. Consulta con nombre de parte → `bloqueada` sin salir a internet.

Registrar fecha, versión del servidor y resultado de cada prueba debajo de esta línea.
