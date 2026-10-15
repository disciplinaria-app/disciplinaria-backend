# Fuentes oficiales: enrutamiento, rutas de lectura y registro

Este módulo indica dónde buscar y cómo dejar constancia. No es fuente jurídica: las rutas internas de los portales cambian, de modo que el enlace concreto se obtiene en cada consulta y se registra el que efectivamente se abrió. Ninguna URL de este archivo autoriza a afirmar que un documento existe sin haberlo abierto.

## 1. Enrutamiento por materia

| Materia | Corporación que se consulta primero | Consulta adicional cuando el tema lo exige |
|---|---|---|
| Disciplinario de abogados (L.1123/2007) | Comisión Nacional de Disciplina Judicial (CNDJ); para la línea anterior a su entrada en funcionamiento (2021), Sala Jurisdiccional Disciplinaria del Consejo Superior de la Judicatura | Corte Constitucional (constitucionalidad de la L.1123, tutela contra providencias disciplinarias) |
| Disciplinario de funcionarios y empleados judiciales (L.1952/2019, mod. L.2094/2021) | CNDJ; Sala Jurisdiccional Disciplinaria para la línea anterior | Corte Constitucional (constitucionalidad del CGD y de la L.2094); Consejo de Estado solo cuando su jurisprudencia sobre el CGD sea pertinente y se declare como tal |
| Tutela, tutela contra providencia judicial y desacato (D.2591/1991) | Corte Constitucional | Corte Suprema y Consejo de Estado cuando actúan como jueces de tutela en la materia; CNDJ cuando la decisión revisada es propia |
| Habeas corpus (L.1095/2006) | Corte Constitucional y Corte Suprema, Sala de Casación Penal | — |
| Penal (L.906/2004; L.600/2000 según el sistema aplicable) | Corte Suprema, Sala de Casación Penal | Corte Constitucional |

El texto de la providencia declara de qué corporación proviene cada subregla. Una subregla de otra jurisdicción se presenta como tal y se justifica su pertinencia; no se le atribuye fuerza vinculante que no tiene en el régimen del caso.

## 2. Portales de jurisprudencia

- **Corte Constitucional**: relatoría en `corteconstitucional.gov.co/relatoria/`, con buscador por número, texto, tema y fecha.
- **Corte Suprema de Justicia**: sistema de consulta jurisprudencial de la Rama Judicial y relatorías por Sala. Seleccionar primero la Sala (Penal, Civil, Laboral, Tutelas).
- **Consejo de Estado**: buscador de jurisprudencia de SAMAI. No confundirlo con la consulta de procesos.
- **CNDJ**: relatoría propia en `relatoria.cndj.gov.co` (paneles «Búsqueda General», «Búsqueda Avanzada» por magistrado, año y número de radicación, temas o descriptor, asunto, y «Búsqueda en Providencia»). La antigua WebRelatoria de `jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/` conserva registros hasta 2022. El portal propio no acepta consultas automatizadas desde el verificador: la consulta a la CNDJ se hace en el navegador del usuario o con documentos que el usuario aporte, y así se declara en el informe.

Orden de consulta sugerido para cada subregla: número o radicado conocido → frase técnica breve de la subregla → categoría + régimen + corporación → mismo concepto con los años de la ventana de actualización → búsqueda adversa (`excepción`, `no procede`, `rectificó`, `modificó`, `apartó`) → seguimiento de las sentencias que cita o que la citan.

## 3. Portales normativos

- **Secretaría General del Senado** (`secretariasenado.gov.co/senado/basedoc/`): texto con notas de modificación, derogatoria y jurisprudencia de constitucionalidad.
- **SUIN-Juriscol** (Ministerio de Justicia y del Derecho, `suin-juriscol.gov.co`): texto, vigencia y afectaciones.
- **Gestor Normativo de Función Pública** (`funcionpublica.gov.co/eva/gestornormativo/`): alternativa oficial.
- Normogramas institucionales (por ejemplo, de entidades públicas que reproducen la ley): reproducción oficial de respaldo cuando las anteriores no respondan; se registra como tal.

Para cada artículo decisivo: leer el texto, las notas de modificación y de inexequibilidad o exequibilidad condicionada, y determinar la versión aplicable a la fecha del hecho o de la actuación. Si los portales discrepan, prevalece el que reproduce el texto con la nota de vigencia más completa, y la discrepancia se reporta.

## 4. Verificador MCP («Verificador jurisprudencial»)

El despacho dispone de un conector propio, desplegado en Google Cloud Run y registrado en claude.ai con el nombre **Verificador jurisprudencial** (servidor `redactar2-verificador`). Antes de usarlo, comprobar que sus herramientas aparecen realmente en la sesión; si no aparecen, no simular su salida y seguir con la búsqueda en navegador.

Herramientas y uso:

| Herramienta | Para qué | Parámetros que importan |
|---|---|---|
| `buscar_providencia` | Candidatos a partir de una subregla abstracta | `tesis` (frase técnica corta, sin datos del caso), `corporacion`, `desde`/`hasta` (años; `hasta` nunca posterior al año en curso), `modo` = `rapido` (dos formulaciones, cabe en una llamada) o `amplio` |
| `verificar_cita` | Confirma identidad de una cita contra el documento oficial | `corporacion`, `tipo_numero` (p. ej. `T-309/2023`, `SU-107/2024`) o `radicado`, y opcionalmente `fecha`, `ponente`, `sala`, `ratio_invocada` (subregla abstracta) |
| `leer_providencia` | Texto oficial por segmentos, con rol estimado de la sección | `identificador` o `url_oficial`, `segmento` (0, 1, 2…), `tamano` |
| `actualizar_linea` | Capa de actualización: ventana de cuatro años desde la fecha de corte | `subregla`, `sentencia_hito`, `corporacion`, `fecha_corte` |
| `estado_verificacion` | Consultar un trabajo pendiente | `trabajo_id` |
| `diagnosticar_portales` | Qué portales responden hoy | ninguno |

Estado de los portales comprobado en vivo (15 de octubre de 2026):

- **Corte Constitucional**: operativo de extremo a extremo (búsqueda por frase, lectura y verificación; comprobado con SU-107/2024 y T-309/2023).
- **Corte Suprema de Justicia** y **Consejo de Estado** (buscador tradicional WebRelatoria): el servidor llega al portal; la búsqueda por texto está en prueba. Si devuelve `sin_resultados` o `parcial`, completar en el navegador.
- **CNDJ**: desactivado en el servidor por decisión del titular, hasta contar con autorización de la entidad. Toda llamada devuelve `portal_no_disponible`; eso no dice nada sobre la existencia de la providencia.

Reglas de lectura de los resultados:

1. Un candidato de `buscar_providencia` sale siempre con `verificado: false`. No se cita sin pasar por `verificar_cita` y `leer_providencia`.
2. En `verificar_cita`, revisar campo por campo. Un `identificador` confirmado con `fecha` discrepante obliga a leer el encabezado con `leer_providencia` y corregir la fecha en el texto; no se acepta el estado global sin mirar los campos.
3. El `pasaje` devuelto es el fragmento más parecido a la `ratio_invocada`, no prueba de que la providencia sostenga la tesis. Leer el contexto y comprobar que pertenece a las razones de la mayoría (`rol` distinto de `salvamento` y `aclaracion`; `solo_en_salvamento: false`).
4. `no_hallada`, `portal_no_disponible`, `timeout` y `sin_resultados` no significan inexistencia. Se reportan con ese nombre y se completa en el navegador.
5. Consultas abstractas: nunca nombres de partes, cédulas, radicados del proceso ni párrafos del borrador. El servidor rechaza con `bloqueada` lo que detecta, pero el filtro no sustituye el cuidado de quien consulta.
6. Cada llamada tiene un tope de 60 segundos. Preferir `modo: rapido`, frases de dos o tres palabras y una corporación por llamada; repetir con otra formulación antes que una sola consulta larga.

## 5. Fallbacks y estados de la consulta

Cuando un portal no responde: (1) reintentar por otra ruta oficial de la misma corporación; (2) descubrimiento web restringido al dominio oficial; (3) documento oficial aportado por el usuario, declarado como tal. Una fuente secundaria (blog, boletín privado, agregador) sirve como pista para localizar, nunca como confirmación: la cita así sostenida se marca `[VERIFICAR: confirmar en fuente oficial …]`.

Distinguir y reportar con precisión: `sin_resultados` (la búsqueda corrió y no halló), `portal_no_disponible`, `bloqueado`, `timeout` y `discrepante`. Ninguno de los cuatro últimos equivale a inexistencia.

## 6. Registro de la consulta

Por cada cita o norma decisiva, conservar para el informe de inserción: corporación o fuente, identificador, URL efectivamente abierta, fecha de consulta, localizador (página o párrafo), estado y, en jurisprudencia, si el pasaje pertenece a las razones de la mayoría. No enviar a buscadores externos nombres de partes, radicados del caso ni párrafos del borrador: la consulta se formula como subregla abstracta.
