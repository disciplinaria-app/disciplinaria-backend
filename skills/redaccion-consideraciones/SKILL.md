---
name: "redaccion-consideraciones"
description: Completa y redacta las consideraciones de providencias judiciales colombianas en las materias del despacho (disciplinario de abogados L.1123/2007 y de funcionarios y empleados judiciales L.1952/2019, penal L.906/2004, tutela, tutela contra providencia judicial y desacato D.2591/1991, habeas corpus L.1095/2006). Úsela SIEMPRE que el usuario entregue una providencia, borrador o Word incompleto y pida terminarlo, completar o estructurar las consideraciones, redactar el caso concreto o la subsunción, ajustar el problema jurídico, o buscar, verificar, insertar o actualizar jurisprudencia o normas. Identifica la materia, va primero a la corporación competente (CNDJ, Corte Suprema, Corte Constitucional) y a las demás si el tema lo exige, lee relatoría y ley en fuente oficial, verifica toda cita en dos capas (línea consolidada + actualización de los cuatro años previos a la fecha de corte) y entrega párrafos listos (Word, archivo o chat). No corrige estilo (lectura-juridica) ni hace el proyecto integral (redactar2).
---

# Redacción de Consideraciones Judiciales

Construye el **fondo** de las consideraciones de una providencia: problema jurídico, marco normativo aplicable, jurisprudencia verificada en su fuente oficial, subsunción y decisión, listos para integrarse al documento. La corrección de estilo corresponde a `lectura-juridica` y se ofrece al final; el proyecto integrado completo (hasta la parte resolutiva) corresponde a `redactar2`.

## Alineación con el Protocolo Despacho LM

La skill aporta el procedimiento; el Protocolo Despacho LM aporta los controles, que prevalecen siempre: jerarquía de fuentes de verdad (expediente > instrucción del chat > protocolo > skill y memoria, con transcripción literal de nombres, radicados y fechas), deliberación proporcional (no se redacta mientras el problema jurídico no esté formulado), tesis contraria de acero, cadena de verificación, lenguaje calibrado y premortem. La jerarquía ordena la autoridad de las instrucciones y de los datos de identificación; no convierte en probado lo que una parte afirma en el expediente.

## Principio rector: nunca inventar

No se fabrican sentencias, radicados, ponentes, fechas, artículos ni textos normativos. Una cita inexistente o un radicado errado exponen al despacho y a quien firma. Por eso toda cita se verifica en la fuente oficial antes de insertarse; lo que no se logra verificar se marca `[VERIFICAR: …]` y se reporta, nunca se presenta como confirmado; las marcas y notas que el borrador ya trae (una cita sin verificar, un «no encontré jurisprudencia») se detectan en la Fase 0 y se resuelven o se informan, nunca se pasan por alto; y los salvamentos de voto no se citan como autoridad salvo que el usuario los invoque como contraste. La regla alcanza a la propia skill: sus plantillas no traen números de sentencia ni remisiones normativas que deban darse por buenas; la jurisprudencia se obtiene siempre en la Fase 2 y los artículos se leen en su fuente en cada encargo.

## Archivos de referencia

| Archivo | Cuándo leerlo |
|---|---|
| `references/fuentes-oficiales.md` | Siempre, antes de la Fase 2: enrutamiento por materia, portales oficiales, rutas de lectura, fallbacks y registro de la consulta. |
| `references/verificacion-jurisprudencial.md` | Siempre, antes de la Fase 2: procedimiento por cita, doble capa, clasificación del hallazgo reciente. |
| `references/estructura-providencias.md` | Fase 0 y Fase 3: plantilla del tipo de acto (tutela, tutela contra providencia judicial, desacato, habeas corpus, disciplinario L.1123 y L.1952, penal). |
| `references/dogmatica.md` | Fase 3: categorías que deben desplegarse por materia, con la guarda de régimen. |
| `references/argumentacion.md` | Fase 3: estándar de profundidad, precedente, formas del argumento, prueba, falacias, léxico. |
| `references/protocolo-lm.md` | Fase 3: principios de redacción del borrador, incluidas las reglas que luego aplica `lectura-juridica`. |

## Flujo de trabajo

### Fase 0 — Lectura y diagnóstico

1. Leer el documento completo. En un expediente largo, leer en este orden: parte resolutiva de primera instancia o acto impugnado, recurso o escrito que fija el objeto, cargos o problema planteado, pruebas, antecedentes.
2. Identificar: tipo de acto y régimen; instancia y etapa (segunda instancia, consulta, desacato, nulidad); qué está completo y qué falta; problema jurídico (planteado, bien planteado, ausente); jurisprudencia y normas que el documento **ya cita** (se conservan salvo error verificado y se someten a verificación como cualquier otra cita); argumentos del recurrente o de las partes que la motivación debe responder.
3. **Barrido de marcas y notas internas del borrador (obligatorio, antes del diagnóstico).** Recorrer el documento completo, incluidas notas al pie, comentarios de Word, control de cambios y texto resaltado o en color, en busca de toda señal dejada por quien lo redactó:

   - notas entre corchetes o paréntesis dirigidas al redactor: `[VERIFICAR…]`, `[PENDIENTE]`, `[COMPLETAR]`, `[CITA]`, `[REVISAR]`, `[CONFIRMAR]`, «no encontré jurisprudencia», «falta cita», «sin soporte», «OJO», «ampliar», «desarrollar»;
   - datos de relleno: `XXX`, `???`, «T-xxx de 20xx», «(fecha)», «[radicado]», «Rad. ___», «M.P. …», párrafos o citas truncados;
   - citas incompletas o sin alguno de sus cinco datos.

   Cada hallazgo se registra con su ubicación y su texto literal, y se trata como una tarea, no como ruido de edición:

   1. **Una nota que dice que no se halló soporte jurisprudencial o normativo revela una afirmación sin respaldo.** Se busca el soporte en fuente oficial. Si aparece, se cita verificado. Si no aparece, la afirmación se reformula con el alcance que las fuentes efectivamente sostienen, o se retira, y se informa. Nunca se borra la nota dejando intacta la afirmación que señalaba.
   2. Una cita incompleta o con datos de relleno se completa desde la fuente oficial o queda marcada `[VERIFICAR: …]` y reportada.
   3. Una instrucción interna («desarrollar», «ampliar con la línea») se ejecuta o se informa como no ejecutada, con la razón.
   4. Ninguna marca se elimina en silencio, y ninguna se conserva en el texto final sin figurar en el informe.

   Si el barrido no encuentra nada, el diagnóstico lo dice expresamente: «ninguna, tras barrido completo». El barrido se repite sobre el texto final antes de entregar.
4. Entregar el diagnóstico en este bloque breve, en el chat:

```
**Diagnóstico**
- Acto y régimen: [tutela de segunda instancia / disciplinario L.1123, apelación / …]
- Corporación de cierre: [Corte Constitucional / CNDJ / CSJ Sala Penal] (+ otras si el tema lo exige)
- Fecha de corte y ventana de actualización: [fecha] · [cuatro años anteriores: AAAA-MM-DD a AAAA-MM-DD]
- Problema jurídico: [planteado como…] / [ausente; se propone: …]
- Argumentos de las partes por responder: [lista corta]
- Jurisprudencia y normas ya citadas: [n citas; se verificarán]
- Marcas y notas internas del borrador: [ubicación · texto literal · tarea que revela] / [ninguna, tras barrido completo]
- Falta por construir: [secciones]
```

### Fase 1 — Encuadre (proporcional)

El insumo más valioso es la **visión del caso** del usuario, a menudo en lenguaje llano ("sí siguió el procedimiento, pero el plazo se demoró; tutelo porque necesita resolución pronta"). La tarea es traducirla a su arquitectura técnica: derecho o deber comprometido y su faceta, subregla que lo sostiene, tipo de decisión que corresponde y órdenes o sanción que la materializan. Si la visión, llevada a su forma técnica, choca con una categoría del régimen (improcedencia tomada por negación; remedio que excede la competencia; "ilicitud sustancial" en un asunto de abogados), se advierte con precisión y se propone el encuadre correcto, sin imponerlo.

Si la visión del usuario descansa en un cómputo de términos (prescripción, caducidad, inmediatez, oportunidad del recurso) o en un dato fáctico, se comprueba con fechas explícitas y aritmética antes de traducirla; una discrepancia se advierte en el encuadre con el cómputo a la vista, y el texto solo afirma lo que las fechas sostienen.

Proporcionalidad: si el documento y la instrucción ya responden al tema, al problema jurídico y a la visión del caso, **no se interroga**; se presenta el encuadre y se procede salvo objeción. Las preguntas, en español y agrupadas, se reservan a lo que el documento no resuelve. "Procede", "adelante" o equivalente cierra la fase sin repreguntas en esa sesión.

**Excepción que no admite el avance automático.** Si el encuadre reformula el problema jurídico planteado en el documento, cambia el sentido de la decisión que el usuario anticipó o advierte un choque de régimen, la skill se detiene y espera confirmación expresa, aunque antes se haya dicho "procede". El problema jurídico no se reescribe sin aviso y aceptación.

```
**Encuadre propuesto**
- Tesis técnica: [la visión del usuario traducida]
- Subreglas por verificar: [una línea por subregla, con corporación esperada]
- Sentido de la decisión: [confirma / revoca / modifica / concede / niega / improcedente]
- Advertencias de encuadre: [ninguna / …]
- ¿Requiere confirmación expresa?: [no / sí: reformula el problema jurídico · cambia el sentido · choque de régimen]
¿Procedo sobre esta base? (Si ya lo indicó y no hay causal de confirmación expresa, se procede.)
```

Distinción que no se confunde en tutela: subsidiariedad o inmediatez incumplidas → **improcedente** (juicio de procedibilidad); ausencia de vulneración → **negar el amparo** (juicio de fondo).

### Fase 2 — Verificación en fuente oficial, en dos capas

Leer `references/fuentes-oficiales.md` y `references/verificacion-jurisprudencial.md` antes de buscar.

**Enrutamiento.** La materia identificada en la Fase 0 decide la primera corporación: CNDJ para disciplinario (Sala Jurisdiccional Disciplinaria del Consejo Superior de la Judicatura para la línea anterior a la entrada en funcionamiento de la CNDJ en 2021); Corte Suprema, Sala de Casación Penal, para penal; Corte Constitucional para tutela, tutela contra providencia judicial y desacato; Corte Constitucional y Corte Suprema, Sala de Casación Penal, para habeas corpus. Las demás corporaciones se consultan cuando el tema lo exige, y el texto declara de cuál proviene cada subregla. La ley se lee en la Secretaría del Senado o en SUIN-Juriscol, con sus notas de modificación, derogatoria e inexequibilidad; un artículo se cita en la versión **aplicable** al hecho o a la actuación, que puede no ser la vigente al consultar.

**Doble capa, para cada subregla:**
- **Capa 1, línea consolidada**: sentencia fundadora o de unificación y los hitos que la desarrollaron. Se conserva siempre; no se elimina por antigua.
- **Capa 2, actualización**: pronunciamientos de los **cuatro años anteriores a la fecha de corte** (la fecha del encargo, salvo que el usuario fije otra; calcular el rango en cada ejecución e incluir los años en la consulta). La ventana no excluye un desarrollo decisivo anterior. El hallazgo se clasifica: **confirma** (se cita en cadena con la fundadora), **precisa** (se citan ambas y el texto muestra la evolución), **modifica** (se advierte al usuario antes de redactar; la línea vigente es el fundamento y la anterior solo contexto) o **tensión no resuelta** (se expone y se advierte; no se presenta como línea pacífica). Sin hallazgo pertinente, se informa "no se localizaron decisiones adicionales en las fuentes y consultas realizadas hasta [fecha]"; la ausencia de resultados no se presenta como prueba de que la línea no varió.

**Por cada cita**, de cualquiera de las dos capas: localizar con el nombre de la corporación en la consulta; abrir la página oficial o el PDF oficial; confirmar allí los cinco datos (corporación, sala o sección, ponente, número o radicado, fecha); extraer la ratio de esa lectura, nunca de un resumen; comprobar que el pasaje pertenece a las razones de la mayoría y no a una reseña de parte, de instancia o de un voto separado; confirmar vigencia y pertinencia. Verificación completa → se inserta con nota al pie. Parcial → `[VERIFICAR: falta confirmar … de …]` y aviso. Nula → no se inserta; se reporta que la tesis necesita respaldo confirmado.

### Fase 3 — Razonamiento, redacción y entrega

Antes de redactar, sin narrarlo: formular el problema jurídico con precisión y descomponerlo si admite subproblemas; construir la **tesis contraria de acero** (la que sostendría el mejor apoderado de la contraparte o un magistrado disidente) y examinarla lealmente con norma, jurisprudencia o prueba. Si la objeción no se supera, la conclusión se reformula o se reduce su alcance, y se advierte al usuario; no se fuerza la refutación.

Redactar con la plantilla del tipo de acto (`references/estructura-providencias.md`), las categorías de la materia (`references/dogmatica.md`), el estándar de argumentación (`references/argumentacion.md`) y los principios de redacción (`references/protocolo-lm.md`). Tres reglas que no se delegan a las referencias:

- **Guarda de régimen.** En L.1123/2007: tipicidad, antijuridicidad como afectación injustificada del deber profesional (art. 4) y culpabilidad; en la voz del despacho no se emplean "bien jurídico" ni "ilicitud sustancial" (una cita auténtica que use otro léxico se conserva y se explica, no se altera). En L.1952/2019: tipicidad, ilicitud sustancial y culpabilidad, con el texto aplicable tras la L.2094/2021; los números de artículo de estas categorías se leen en la fuente oficial en cada encargo. En penal: conducta punible; el estándar del art. 381 L.906 rige la sentencia condenatoria, no toda decisión penal. No se transfieren categorías entre regímenes.
- **Argumentar, no exponer.** Cada subregla se enuncia, se funda en su ratio y se aplica por subsunción explícita; cada argumento relevante de las partes se responde en su mejor versión; la prueba se valora con la regla de la sana crítica identificada. La cita que no se aplica al caso es adorno y se elimina.
- **Lenguaje calibrado y extensión proporcional.** Lo verificado se afirma; lo probable se declara probable; lo no verificado se marca o se excluye. Un auto de trámite no recibe la motivación de una sentencia.

Antes de entregar: **cadena de verificación** (toda afirmación verificable del borrador —citas, artículos y su versión aplicable, datos del expediente— contrastada contra su fuente) y **premortem** (si esta providencia fuera revocada en alzada o dejada sin efecto por vía de tutela contra providencia judicial, por qué; reforzar ese punto).

**Entrega según el entorno:**
- *Documento abierto en Word*: insertar los párrafos directamente en el lugar que corresponde, sin control de cambios, con las citas a pie de página en el formato que el documento ya use, y releer el documento guardado para comprobar la inserción.
- *Archivo .docx adjunto*: trabajar sobre una copia con la skill `docx`, insertar en el lugar correspondiente y devolver el archivo.
- *Texto pegado o sin documento*: entregar los párrafos en la respuesta, con las notas al pie numeradas al final del bloque. No afirmar inserción que no se realizó.

El texto destinado a la providencia va en prosa continua, sin viñetas, en tercera persona impersonal, presente para el análisis y las normas, pasado para las actuaciones; nombres, radicados, fechas y calidades procesales se transcriben del expediente.

**Informe de inserción** (en el chat, separado del texto de la providencia, siempre):

```
**Informe de inserción**
- Párrafos insertados: [sección y posición]
- Citas verificadas: tabla con corporación · sala · ponente · número/radicado · fecha · fuente abierta (URL oficial, verificador MCP o documento aportado por el usuario) · estado
- Marcas del borrador recibido: [cada una → resuelta (cómo y con qué fuente) / afirmación reformulada o retirada / subsiste (por qué)] o "ninguna, tras barrido completo"
- Marcas [VERIFICAR] pendientes en el texto entregado: [lista o "ninguna", tras repetir el barrido]
- Normas citadas y versión aplicable: [artículo · versión aplicada según nota de modificación · observación]
- Tesis contraria considerada y cómo se cerró: [dos líneas]
- Premortem: [punto más vulnerable y qué se reforzó]
- Capa de actualización: [subregla → confirma / precisa / modifica / tensión / no se localizaron decisiones adicionales hasta (fecha)]
```

Cerrar con: "¿Deseas que aplique la corrección de estilo editorial (`lectura-juridica`) sobre los párrafos insertados?"

## Lista de control final

- Documento leído completo; jurisprudencia y normas preexistentes inventariadas y verificadas.
- Barrido de marcas hecho sobre el borrador recibido y repetido sobre el texto final; cada nota interna resuelta o informada; ninguna afirmación que el redactor marcó como sin soporte quedó en pie sin fuente verificada.
- Materia identificada y corporación de cierre consultada primero; subreglas de otras corporaciones declaradas como tales.
- Toda cita con sus cinco datos tomados de la página o el PDF oficial (o del conector «Verificador jurisprudencial», con `verificar_cita` sin campos discrepantes, o de un documento aportado por el usuario y así declarado); ninguna desde un resumen, boletín o blog; ninguna de memoria.
- Doble capa ejecutada por subregla, con la ventana de cuatro años calculada desde la fecha de corte y el hallazgo clasificado; la línea fundadora conservada.
- Artículos citados en su versión aplicable, con la nota de modificación o inexequibilidad reportada cuando afecta el caso.
- Guarda de régimen respetada; improcedencia y negación del amparo no confundidas; sin analogía in malam partem; sin salvamentos como autoridad.
- Problema jurídico reformulado solo con confirmación expresa del usuario.
- Tesis contraria construida y examinada; argumentos de las partes respondidos; prueba de descargo valorada; falacias controladas.
- Datos del expediente transcritos, no reconstruidos.
- Entrega en el formato del entorno, en prosa continua, con informe de inserción y oferta de `lectura-juridica`.
