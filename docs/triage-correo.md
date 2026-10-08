# Triage de correspondencia del correo institucional

## Qué resuelve

El sistema responde a un problema concreto: la correspondencia que llega al
correo institucional no se puede valorar por el asunto del mensaje. El asunto
arrastra el texto del oficio original, de modo que una respuesta puede parecer
pertinente cuando en realidad proviene de otra entidad, cita otro radicado o
devuelve el asunto por falta de competencia. El dato decisivo suele estar en el
PDF adjunto, y con frecuencia en un PDF escaneado.

El módulo no produce un resumen literario del documento: extrae datos
verificables y **confronta** lo recibido con lo que el despacho había enviado.
La alerta, no la síntesis, es su producto principal.

## Reparto entre lo verificable y lo interpretativo

El diseño separa deliberadamente las dos operaciones:

| Operación | Dónde se resuelve | Razón |
|---|---|---|
| Comparación de la entidad que suscribe | `services/cotejo.py` | Reproducible y auditable |
| Comparación de radicados | `services/cotejo.py` | Reproducible y auditable |
| Cómputo de días del término | `services/triage.py` | Un término mal contado no es tolerable |
| Identificación de quién suscribe | `agents/agente_triage.py` | Exige lectura del documento |
| Materia sustancial y tipo de acto | `agents/agente_triage.py` | Exige lectura del documento |
| Redacción de la ficha para su lectura | `services/presentacion.py` | Común a las tres rutas |

El agente nunca cuenta días: solo señala la fecha límite que el documento
expresa, y los días los calcula el código. Si devuelve una fecha en formato no
interpretable, el término se descarta y se advierte, antes que entregar un plazo
equivocado.

Cuando el cotejo y el agente concurren en un mismo hallazgo, la alerta se marca
con origen `AMBOS` y conserva la severidad mayor. La urgencia final nunca queda
por debajo de la alerta más grave, aunque el agente haya propuesto una menor.

### Por qué la comparación de entidades no opera por subcadenas

«previsora» es subcadena de «fiduprevisora». Una comparación por subcadenas
tomaría a La Previsora S.A. y a Fiduprevisora S.A. por la misma entidad y
silenciaría precisamente la alerta que se espera. El cotejo compara, por ello,
núcleos léxicos completos tras suprimir diacríticos, puntuación, formas
societarias y descriptores genéricos («Compañía de Seguros», «Sociedad
Fiduciaria»). El caso está cubierto por prueba en `tests/test_cotejo.py`.

El criterio general es: **ante la duda, alertar**. Un falso positivo cuesta una
verificación de medio minuto; un falso negativo cuesta advertir el error cuando
ya precluyó la oportunidad de corregirlo.

## Documentos escaneados

Buena parte de la correspondencia de las entidades llega como oficio suscrito y
digitalizado, sin capa de texto. La extracción directa devuelve vacío, de modo
que el reconocimiento óptico no es un accesorio: sin él el sistema fallaría con
los documentos más relevantes.

`services/extraccion_pdf.py` extrae primero la capa de texto nativa y aplica
reconocimiento óptico **solo** a las páginas cuyo texto resulta insuficiente
(menos de 120 caracteres útiles). El método empleado queda registrado por
documento: `TEXTO_NATIVO`, `OCR`, `MIXTO` o `NINGUNO`.

Si el reconocimiento óptico no está instalado, el procesamiento no se
interrumpe: se declara como advertencia explícita. La distinción importa, porque
«el documento no dice nada» y «no se pudo leer el documento» tienen
consecuencias opuestas para el destinatario.

Límites vigentes: 80 páginas por documento, 20 páginas por reconocimiento
óptico, 25 MB por adjunto, 40 MB y 10 adjuntos por solicitud.

## Endpoints

### Acceso

Los dos endpoints de clasificación exigen una clave compartida en la cabecera
`X-API-Key`, o bien como `Authorization: Bearer <clave>`. Las claves válidas se
declaran en `TRIAGE_API_KEYS`, separadas por comas para poder rotarlas sin
interrumpir el servicio. **Si no hay ninguna configurada, los endpoints
rechazan toda solicitud**: fallar cerrado es preferible a dejar abierto un
endpoint que consume el modelo y recibe correspondencia.

`GET /correo/diagnostico` no exige clave, para que el despliegue pueda
verificarse antes de configurarla, y no revela dato alguno de la
correspondencia.

### `POST /correo/triage` — multiparte

Para una capa de ingesta que puede remitir archivos: los PDF viajan como
adjuntos de formulario.

Campos: `remitente` (obligatorio), `asunto`, `cuerpo`, `fecha_recepcion`,
`entidad_interpelada`, `radicado_enviado`, `asunto_enviado`, `aplicar_ocr`,
`archivos`.

### `POST /correo/triage/json` — una sola solicitud JSON

Para una capa de ingesta que no puede construir una solicitud multiparte, como
un flujo de Power Automate. Cada adjunto viaja en `contenido_base64` —y el
servidor lo extrae, con reconocimiento óptico si viene escaneado— o bien ya
convertido a `texto`. El cuerpo del correo admite `cuerpo_base64` como
alternativa a `cuerpo`, porque el HTML de Outlook contiene comillas y saltos de
línea que pueden romper una plantilla JSON.

Los adjuntos que no son PDF se enuncian en `adjuntos_no_analizados` sin
someterlos a extracción, de modo que la capa de ingesta puede remitir cuanto
venía en el correo sin provocar alertas de ilegibilidad espurias.

### `GET /correo/diagnostico`

Informa si el reconocimiento óptico está instalado. **Conviene consultarlo tras
cada despliegue**: si `ocr_disponible` es `false`, los PDF escaneados no se
analizarán y el sistema lo advertirá documento por documento, pero la capacidad
estará perdida hasta que se corrija el entorno.

## La ficha que se devuelve

```
entidad_remitente     quién suscribe el documento
tipo_acto             RESPUESTA_DE_FONDO | ACUSE_DE_RECIBO | REQUERIMIENTO |
                      TRASLADO | NOTIFICACION | CITACION | CONSTANCIA |
                      DEVOLUCION_POR_COMPETENCIA | PUBLICIDAD | OTRO
materia               de qué trata realmente el adjunto
resumen               síntesis y consecuencia para el despacho
radicados             radicados citados, tal como aparecen
requiere_actuacion    si exige actuación, y cuál
termino               fecha límite y días restantes calculados
alertas               catálogo cerrado, con severidad y origen
urgencia              ALTA | MEDIA | BAJA
documentos            trazabilidad de la extracción de cada adjunto
adjuntos_no_analizados  adjuntos que no son PDF, enunciados sin extracción
cotejo                resultado de la verificación determinista
redaccion             asunto, texto y HTML ya compuestos para remitir
advertencias          limitaciones del procesamiento
```

### Catálogo de alertas

| Código | Significado |
|---|---|
| `ENTIDAD_DISTINTA` | La entidad que responde no es la interpelada |
| `DEVOLUCION_POR_COMPETENCIA` | La entidad no se declara competente o advierte un envío errado |
| `RADICADO_NO_COINCIDE` | El radicado citado no corresponde al remitido |
| `TERMINO_CORRIENDO` | El documento fija o activa un término |
| `REQUIERE_RESPUESTA` | Exige respuesta o actuación |
| `DOCUMENTO_ILEGIBLE` | No se recuperó el texto del adjunto |
| `DOCUMENTO_INCOMPLETO` | El documento remite a anexos ausentes |
| `SIN_SUSCRIPCION` | No aparece suscrito por funcionario identificable |
| `SIN_ADJUNTO_ANUNCIADO` | El correo anuncia un adjunto que no llegó |
| `DATO_RESERVADO` | Parece contener información reservada o datos sensibles |

El catálogo es cerrado: si el agente propone un código ajeno, se descarta y se
consigna en `advertencias`. Lo mismo ocurre con un tipo de acto no catalogado,
que se registra como `OTRO`.

## Tratamiento de la información

El texto de los adjuntos se usa en memoria para el análisis y **no se devuelve
ni se almacena**: la respuesta contiene solo la ficha estructurada. El campo
está excluido de la serialización por el esquema, no por omisión del cliente, y
una prueba lo verifica.

Dos advertencias que deben considerarse antes de conectar el buzón
institucional:

1. La correspondencia puede contener información sujeta a reserva de la
   actuación disciplinaria y datos personales protegidos por la Ley 1581 de
   2012. Cualquier ruta de ingesta implica transmitir ese contenido a un
   proveedor externo de modelos de lenguaje. Se recomienda limitar el
   procesamiento a correspondencia administrativa y excluir por regla los
   correos provenientes de los flujos de expedientes.
2. La ficha es un instrumento de triage, no un sustituto de la lectura del
   documento. Las advertencias existen para que el lector sepa cuándo la ficha
   se construyó sobre material incompleto, truncado o ilegible.

## La capa de ingesta

Este módulo recibe correos; no los busca. Esa es tarea de la capa de ingesta,
que se conecta al buzón y alimenta los endpoints de arriba.

**Ruta implementada: reenvío a un buzón propio** (`ingesta/`). Una regla del
correo institucional reenvía la correspondencia a un buzón propio del sistema,
y un worker lo sondea, clasifica y remite la ficha. No exige intervención del
área técnica ni credenciales del buzón institucional. Su configuración, sus
garantías y sus límites están en [ingesta-reenvio.md](ingesta-reenvio.md).

```bash
python -m ingesta.worker --una-vez   # un ciclo y termina
python -m ingesta.worker             # sondeo permanente
```

**Ruta preparada: Power Automate dentro del tenant institucional.** No envía
correspondencia a un buzón externo ni expone credenciales, lo que la hace la
más defendible institucionalmente. El endpoint `/correo/triage/json` está
dispuesto para ella: acepta los adjuntos y el cuerpo en base64, devuelve la
ficha ya redactada y exige clave de acceso. El flujo son cinco acciones y no
requiere escribir código; su configuración está en
[ingesta-power-automate.md](ingesta-power-automate.md). La acción HTTP es de
licencia premium, lo que debe verificarse antes de comprometerse con ella.

**Ruta posible, no implementada: worker propio sobre Microsoft Graph.** Más
flexible y sin dependencia de licencias, pero exige que el área técnica
registre una aplicación en el directorio o habilite IMAP con contraseña de
aplicación.

Todas consumen el mismo núcleo. Los módulos de `services/` son comunes a
ellas: cambiar de ruta es sustituir la capa de ingesta, no rehacer el sistema.

## Pruebas

```bash
pip install -r requirements-dev.txt
pytest tests/ -q
```

La batería cubre el cotejo determinista, la normalización del cuerpo del correo,
la extracción de PDF nativos y escaneados —incluido el reconocimiento óptico de
extremo a extremo sobre un PDF generado sin capa de texto—, las garantías del
orquestador y los endpoints. El agente se sustituye por una función controlada:
las pruebas no consumen la API del modelo.

Las pruebas de reconocimiento óptico se omiten automáticamente si tesseract no
está instalado en el entorno.

## Despliegue

`nixpacks.toml` instala `tesseract` y `poppler_utils`, que no vienen en la
imagen base de Railway. Tras desplegar, consultar `GET /correo/diagnostico`
para confirmar que el reconocimiento óptico quedó operativo.

Variable opcional: `MODEL_TRIAGE` permite asignar al triage un modelo distinto
del que usan los cinco agentes de análisis. Por defecto emplea el mismo, para no
degradar la detección de incongruencias sin medirla antes.
