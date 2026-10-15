# REDACTAR2 · PROVIDENCIA INTEGRAL

**Versión 1.2 — 15 de octubre de 2026**

## Qué entrega este paquete

Una sola skill que integra `redaccion-consideraciones`, `lectura-juridica` y las reglas de uso del conector descrito en `SPEC-redactar2-mcp.md`. Su tarea principal es **terminar el proyecto de providencia**, desde la lectura de los insumos hasta una motivación aplicada, parte resolutiva congruente y revisión editorial completa.

No es un servidor MCP ni una aplicación que, por sí sola, acceda a Word o a portales. Es un paquete de instrucciones, referencias y controles para un asistente con las herramientas correspondientes. La disponibilidad y los permisos del entorno determinan qué operaciones puede ejecutar realmente.

La exigencia de profundidad se concreta en soportes y respuestas comprobables, no en promesas de que una decisión sea «incuestionable». El resultado siempre es un proyecto para revisión del funcionario judicial.

## Uso principal

Importar **una sola** de las versiones empaquetadas en el entorno que admita skills. `skill.zip` es el paquete principal; la copia `.skill`, si se entrega, contiene exactamente los mismos bytes con la extensión observada en las originales. No instalar ambas como si fueran funciones distintas. El punto de entrada es `redactar2/SKILL.md`.

No activar simultáneamente las originales para la misma tarea integral: esta versión ya incorpora sus funciones y resuelve sus divergencias. No las desinstala ni modifica automáticamente.

Aportar borrador y piezas pertinentes. Si ya se explicó la visión del caso, reutilizarla. No es necesario rellenar manualmente las matrices: el asistente debe construirlas a partir del trabajo realizado.

### Instrucción de activación

> Aplica Redactar2 en modo integral y termina esta providencia. Lee el borrador y las piezas suministradas, verifica las fuentes oficiales, examina mi tesis frente a la mejor objeción, reorganiza lo necesario y completa consideraciones, caso concreto y parte resolutiva. Ejecuta también la lectura editorial y el control de cierre. Conserva los datos y citas que deban permanecer literales, registra las correcciones sustanciales y entrega el proyecto integrado con las reservas indispensables por separado. No te detengas para pedir autorizaciones rutinarias ni afirmes haber editado Word si no lo hiciste.

El encargo simple «termina esta providencia» también está comprendido en el activador del archivo principal.

## Los ocho pasos del flujo

| Fase | Resultado exigido |
|---|---|
| 0. Alcance y lectura | Inventario de lo disponible, cobertura real y apartados pendientes. |
| 1. Hechos y controversia | Fuentes localizadas, cronología, distinción entre alegación y prueba, mapa de argumentos. |
| 2. Derecho aplicable | Régimen, competencia, temporalidad, estándar y problemas delimitados. |
| 3. Investigación | Búsqueda oficial multicanal, identidad y contenido de las citas, actualización y precedente adverso examinados. |
| 4. Argumentación | Reglas aplicadas, prueba valorada, objeciones respondidas y tesis corregida si es necesario. |
| 5. Redacción | Proyecto integrado y determinaciones congruentes. |
| 6. Lectura editorial | Gramática, sintaxis, linealidad, economía e integridad de datos y citas. |
| 7. Cierre | Revisión adversarial, edición real y comprobación de la versión final. |

Las ocho puertas de calidad G0-G7 exigen comprobar cada etapa, no darla por finalizada por el solo hecho de haber redactado un texto. Sus controles se detallan en `references/control-cierre.md`.

La capa de actualización jurisprudencial se calcula en cada ejecución sobre los **cuatro años anteriores a la fecha de corte**; no hay un año fijo en el paquete.

## Controles de mayor importancia

**Una cita existente puede estar mal utilizada.** Se separan identidad, contexto, atribución a la mayoría, regla, pertinencia y actualidad. Se exige lectura contextual; el conector no decide por el redactor si una ratio gobierna el caso.

**Tu visión se examina, no se obedece ciegamente.** Si una objeción fundada o una prueba adversa altera el resultado, la skill debe ajustar la conclusión y explicarlo. La revisión crítica no está obligada a dar siempre la razón a la tesis inicial.

**El régimen se comprueba.** Se separan Ley 1123, Ley 1952 y sus modificaciones, Ley 600, Ley 906 y actuaciones constitucionales. Los módulos son guías de verificación, no sustitutos de las normas aplicables.

**Forma y fondo se integran sin confundirlos.** El modo integral incluye corrección editorial y reorganización; el modo exclusivamente editorial no permite cambiar el sentido o introducir hechos nuevos. Los cambios sustanciales verificados se reportan.

**La resolutiva se contrasta en ambas direcciones.** Cada determinación debe derivar de la motivación; cada conclusión que exija decisión debe reflejarse en la resolutiva. No se inventan destinatarios, plazos, recursos o efectos.

**La certeza se calibra.** Lo no corroborado no se presenta como verificado; los bloqueos no desaparecen por una declaración genérica de calidad. No se confunde proyecto completo con providencia firmada o adoptada.

## Herramientas y entorno

Si hay Word conectado, la skill ordena insertar y comprobar el resultado con las herramientas efectivas. Si solo hay archivos, trabajar en una copia y entregar el archivo producido. Si no hay editor, entregar texto integrado y reconocer que no se insertó.

Si existe el MCP previsto, utilizar sus cinco operaciones descubiertas en el entorno. Si no existe, recurrir a fuentes oficiales mediante herramientas de consulta disponibles. Si tampoco hay acceso externo, no fingir verificación actual: completar lo sustentado e identificar reservas.

El paquete no incluye credenciales, endpoints activos ni infraestructura. Los detalles de conexión deben corresponder al servicio real, no a suposiciones extraídas de la especificación.

## Auditor local y evidencia de prueba

`auditar_entrega.py` revisa inventario, enlaces, campos de soporte, estados pendientes, protecciones literales, cambios reportados y declaraciones de entrega. Funciona sin red y no modifica el documento fuente.

Se incorporan **51 pruebas automatizadas** (44 del auditor estructural y 7 del contrato de búsqueda multicanal) y un plan separado de **27 escenarios adversariales** para evaluar la skill en un entorno real. Las 51 pruebas se ejecutaron durante la construcción; el resultado detallado figura en `tests/resultado-ejecucion.txt`. Los 27 escenarios son un plan, no se presentan como pruebas ejecutadas del asistente en Word.

Un resultado estructural satisfactorio **no acredita** verdad de las pruebas, existencia de las citas, corrección jurídica ni exhaustividad del inventario. El control no sustituye el contraste de fuentes ni la revisión judicial. Las URLs y citas de los tests son sintéticas y no deben usarse en providencias.

## Archivos principales

`SKILL.md` contiene el flujo y activador; `references/` desarrolla los módulos; `assets/control-entrega.json` es la plantilla de trazabilidad; `scripts/auditar_entrega.py` ejecuta controles estructurales; `tests/` conserva pruebas de código; `assets/originales/` y `assets/manifiesto-origen.json` preservan procedencia. El registro de cambios explica las modificaciones respecto de tus originales.

Se conservaron los cinco módulos nominales de la original de redacción y se ampliaron sus controles. No se necesita que el asistente cargue todos los módulos a la vez: el punto de entrada le indica cuál leer en cada fase.

## Estado real de esta entrega

Paquete creado y sometido a pruebas locales del auditor, revisión de estructura y empaquetado. No se instaló en una cuenta, no se editó una providencia real, no se desplegó el MCP y no se probó el flujo completo en Word. Esa distinción forma parte de las propias reglas de honestidad de ejecución del paquete.

## Herramientas externas

La integración operativa se documenta en `references/herramientas-externas.md`. El paquete diferencia expresamente la skill de redacción del conector remoto y de los mecanismos de navegador. La mera instalación del ZIP no instala Playwright, Hyperresearch ni un MCP remoto. Para producción, `redactar2-mcp` debe estar desplegado y autenticado; Playwright se recomienda como adquisición interna para portales dinámicos. Playwright y Hyperresearch se integran expresamente como **multiplicadores de la búsqueda oficial**: Playwright abre y automatiza relatorías dinámicas; Hyperresearch aporta amplitud, seguimiento de citas, contradicciones, gap-fill y cite-check. `vercel-labs/skills` permite incorporar y mantener esas capacidades en agentes compatibles. La autoridad final sigue siendo la fuente oficial.
