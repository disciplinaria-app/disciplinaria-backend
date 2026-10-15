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

## Comprobado en vivo (octubre de 2026)

**Corte Constitucional.** La búsqueda funciona por URL
`/relatoria/buscador-jurisprudencia/texto/{desde}/{hasta}/{frase}/0/0`; los
resultados se pintan en `#tabla-resultado` con enlaces
`/relatoria/{año}/{TIPO}-{num}-{aa}.htm` (autos en `/relatoria/Autos/…`), «Tema:» y
«Fecha de providencia AAAA-MM-DD». SU-107/2024 se verificó de extremo a extremo.

**WebRelatoria (CNDJ, CSJ, Consejo de Estado tradicional).**
- Campos ocultos bajo el panel «Criterios de búsqueda»; solo `searchForm:temaInput`
  tiene id estable; «Texto Completo» se localiza por su rótulo.
- Las filas son `tbody[id$='jurisTable_data'] tr[data-rk]` con un
  `span[id$=':descrip']` (FECHA dd/mm/aaaa, PONENTE, DEMANDANTE, DEMANDADO,
  DESCRIPTOR-RESTRICTOR). No muestran radicado: se lee en la «titulación»
  (botón `tituIcon` → `[id$='dialogInfoPanel']`). Los nombres de las partes no se
  copian al fragmento del candidato.
- Sin resultados: diálogo `[id$='dialogMessPanel']` «No se encontraron resultados…».
- Como el portal no tiene URL por providencia, `url_oficial` del candidato lleva
  `#wr?consulta=…&rk=…`; `leer_providencia` repite la búsqueda y abre la fila con
  el botón HTML (o Word). Pendiente de confirmar en vivo: que el texto escrito en
  «Texto Completo» se envíe (el adaptador informa `campo`, `valor` y `sentencia`
  en `detalle`) y el formato en que llega el documento.
