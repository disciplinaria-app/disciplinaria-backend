# Procedencia e integración: qué se conservó y qué cambió

## 1. Material realmente examinado

- `redaccion-consideraciones.skill`: archivo principal y los cinco módulos de argumentación, dogmática, estructura, protocolo y verificación.
- `lectura-juridica.skill`: archivo principal completo de corrección editorial y mejora de coherencia.
- `SPEC-redactar2-mcp.md`: especificación completa del conector verificador.

Los dos archivos `.skill` aportados son contenedores ZIP. Se extrajeron para lectura, sin ejecutar su contenido. Las copias de procedencia dentro del paquete se preservan como `.txt` para no generar múltiples puntos de entrada. No son instrucciones operativas activas. Consultar `assets/manifiesto-origen.json` para huellas y rutas.

## 2. Conservado de las originales

Conservar lectura previa, diagnóstico de lo pendiente, visión del usuario traducida a problema técnico, diferenciación de regímenes, verificación de identidad, doble capa jurisprudencial, subsunción expresa, prueba de descargo, mejor objeción, corrección editorial, tiempos verbales por sección e integridad de citas y datos. Retener los cinco nombres de módulos de la original de redacción con contenido integrado y ampliado.

## 3. Cambios deliberados, no atribuidos a las fuentes

| Punto de las originales | Decisión de integración |
|---|---|
| Redacción de fondo y lectura editorial separadas con ofrecimiento posterior | Ejecutar ambas automáticamente cuando el usuario encargue terminación integral. Mantener límites en encargo exclusivamente editorial. |
| Confirmaciones obligatorias aunque el contexto ya sea suficiente | Preguntar solo por incertidumbres esenciales no resolubles con los insumos; no repetir datos conocidos. |
| Finalizar tras insertar párrafos | Exigir proyecto integrado, caso concreto, resolutiva y verificación posterior del resultado. |
| Jerarquía «expediente > chat > protocolo» | Separar autoridad de instrucciones, valor probatorio de piezas y fuentes del derecho; no tratar toda afirmación del expediente como verdad. |
| Refutar necesariamente la tesis contraria | Examinarla lealmente; permitir que venza y obligue a corregir la tesis propuesta. |
| Verificar cinco datos y leer la ratio en la fuente oficial | Separar identidad, autoría de la proposición, contexto, regla, pertinencia y evolución. |
| Permitir dos fuentes secundarias para confirmación | Adoptar la restricción oficial del MCP: las secundarias son pistas, no fuente de confirmación. |
| Marcas de verificación dentro del texto insertado | Admitirlas solo durante trabajo; no llamar cerrado a un proyecto con soporte decisivo pendiente. Mantener reservas fuera de la voz judicial. |
| Prohibición lexical absoluta de ciertas expresiones en Ley 1123 | Mantener nomenclatura propia en la redacción, sin censurar citas auténticas ni afirmar exclusividades terminológicas no comprobadas. |
| Conservar toda jurisprudencia fundacional sin matiz | No eliminar por antigüedad; corregir o excluir lo errado, superado o impertinente con registro. |
| Solo reconocer cambio por declaración expresa | No presumir cambio; tampoco continuidad por ausencia de fórmula. Examinar tensiones y mantener reservas cuando no se resuelvan. |
| Actualización centrada en fallos que citan al hito | Agregar búsqueda independiente, excepciones y precedentes adversos. |
| Requisitos probatorios generales y pluralidad de indicios sin matiz | Exigir estándar propio de régimen y etapa; no imponer cantidad universal de indicios. |
| Conservar todo texto sin omisión | Preservar toda información relevante; permitir eliminar duplicidades y corregir errores con trazabilidad. |
| Priorizar menos puntos y más nominalizaciones | Aplicar preferencia con criterio, sin oraciones interminables ni nominalizaciones que oscurezcan. |
| Inserción directa asumida en Word | Descubrir capacidad real, guardar versión y releer; si no hay editor, entregar texto sin fingir inserción. |
| Calidad expresada como nivel de alta corte | Traducirla a controles observables de cobertura, evidencia, inferencia, objeción y congruencia; no prometer infalibilidad. |

## 4. Ampliaciones originales de esta versión

Agregar inventario de cobertura, clasificación de afirmaciones, control de temporalidad y estándares por acto; mapas argumento-problema-respuesta y problema-determinación; prueba adversarial; manejo de archivos y reanudación; protección ante instrucciones insertadas en fuentes; minimización de datos; ocho puertas de cierre; auditor local con pruebas sintéticas y estados honestos de entrega.

Ampliar los itinerarios a desacato, Ley 600 y otros actos con verificación del régimen, sin afirmar que las originales ya contenían todo ese desarrollo. No añadir citas judiciales de muestra a la base operativa.

## 5. Qué no se implementó ni se afirma

No se implementó el servidor MCP, ni su pipeline, scraping, autenticación, caché, base de datos o despliegue. No se instaló la skill en una cuenta ni se modificó un documento Word real. El auditor local no es el verificador de citas. Las pruebas unitarias no constituyen validación judicial ni prueba de comportamiento del modelo ante expedientes reales.

La copia `.skill` de esta entrega, cuando se suministra, es el mismo ZIP con otra extensión, siguiendo el contenedor observado en las originales. No es una garantía de compatibilidad con toda versión de una plataforma. Usar el formato admitido por el entorno de destino.

## Integración de herramientas externas — revisión 2026-09-28

Se evaluaron los repositorios `lackeyjb/playwright-skill`, `jordan-gibbs/hyperresearch` y `vercel-labs/skills`, además de `microsoft/playwright-mcp` y `firecrawl/firecrawl-mcp-server`. Se añadieron `herramientas-externas.md` y `busqueda-jurisprudencial-oficial.md`. La decisión arquitectónica es mantener un solo conector jurídico público (`redactar2-mcp`) y usar esas herramientas como **multiplicadores de la capacidad de búsqueda oficial**: Playwright para automatizar relatorías dinámicas; Hyperresearch para amplitud, seguimiento de citas, contradicciones, gap-fill, procedencia y cite-check; Vercel Skills para incorporar y mantener capacidades de agentes; y Firecrawl/buscadores como descubrimiento auxiliar. La autoridad final continúa siendo el texto oficial recuperado y verificado. El paquete incorpora además `assets/SPEC-redactar2-mcp-v2.md` como especificación técnica revisada para trasladar esa arquitectura al servidor de producción.

## Revisión 2026-10-15 — alineación con `redaccion-consideraciones` v2

Cambios aplicados en esta versión (1.2), en respuesta a la revisión conjunta de las dos skills:

| Punto | Antes | Ahora |
|---|---|---|
| Ventana de actualización | «desde 2022 hasta la fecha de corte», fijada en cuatro módulos | Cuatro años anteriores a la fecha de corte, calculados en cada ejecución (SKILL.md Fase 3, `verificacion-jurisprudencial.md`, `busqueda-jurisprudencial-oficial.md`, `herramientas-externas.md`). La fecha fija dejaba de ser móvil con el paso de los años. |
| Pausa en modo integral | Ninguna pausa rutinaria | Dos excepciones expresas en Fase 2: inversión del sentido anticipado por el usuario y régimen/estándar/competencia desmentidos por la verificación. Escenario 25 del plan adversarial. |
| Guarda entre Ley 1123 y Ley 1952 | Tratada por separado en cada apartado | Párrafo de guarda cruzada en `dogmatica.md` §2 y referencia en SKILL.md Fase 2; escenario 27. |
| Estándar probatorio | «no importar mecánicamente el estándar de otro régimen» | Añadida la exclusión expresa de categorías de otros sistemas («preponderancia»). |
| Fecha de corte histórica | Tratada en `derecho-aplicable.md` §2 | Escenario 26 la convierte en prueba de comportamiento. |
| Línea anterior a la CNDJ | No enrutada | `busqueda-jurisprudencial-oficial.md` remite a la relatoría de la Sala Jurisdiccional Disciplinaria del CSJ para decisiones anteriores a 2021. |

No se modificaron el auditor, sus tests ni la especificación del MCP. `assets/originales/` conserva las copias de la versión anterior de `redaccion-consideraciones`; la versión v2 de esa skill (con `fuentes-oficiales.md` y las plantillas de desacato y tutela contra providencia) se distribuye como skill independiente y no se replica aquí, porque esta skill ya contiene sus equivalentes en `estructura-providencias.md` §3-4 y `busqueda-jurisprudencial-oficial.md`.

## Versión 1.3 (15 de octubre de 2026)

- El conector verificador pasó de especificación a servicio desplegado (Google Cloud Run, conector «Verificador jurisprudencial»). `mcp-y-herramientas.md` describe sus operaciones reales, parámetros y estado por portal.
- Corte Constitucional comprobada en vivo de extremo a extremo; Corte Suprema y Consejo de Estado alcanzables con búsqueda en prueba; CNDJ desactivada en el servidor hasta autorización de la entidad.
- Fase 3 indica el orden de uso del conector y la vía de respaldo en navegador.
