# Ingesta con Power Automate

Esta es la ruta institucionalmente más defendible: el flujo corre dentro del
tenant de Microsoft 365, no envía correspondencia a un buzón externo y no
expone las credenciales del buzón institucional. Solo sale del tenant la
llamada al endpoint de clasificación.

El flujo consta de cinco acciones y no requiere escribir código.

## Lo que debe verificarse antes de empezar

**La acción HTTP de Power Automate es de licencia premium.** Es el único medio
por el que un flujo puede llamar a un endpoint propio; sin ella esta ruta no es
viable. Compruébelo antes que nada: cree un flujo de prueba y busque la acción
«HTTP». Si aparece marcada como premium y su licencia no la cubre, la ruta de
reenvío documentada en [ingesta-reenvio.md](ingesta-reenvio.md) es la
alternativa.

## Paso 1. Generar y configurar la clave de acceso

Los endpoints de triage exigen una clave compartida. Sin ella configurada
rechazan toda solicitud: un endpoint que consume el modelo y recibe
correspondencia no puede quedar abierto por omisión.

Genere una clave:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Defínala en las variables del servicio de Railway como `TRIAGE_API_KEYS`. Se
admiten varias separadas por comas, de modo que pueda rotarlas sin interrumpir
el servicio: agregue la nueva, actualice el flujo, retire la antigua.

La clave viaja en la cabecera `X-API-Key`. También se admite como
`Authorization: Bearer <clave>`, porque no toda capa de ingesta permite
cabeceras arbitrarias.

Verifique luego que el reconocimiento óptico quedó instalado:

```bash
curl https://<su-app>.up.railway.app/correo/diagnostico
```

Ese endpoint no exige clave —para que el despliegue pueda verificarse antes de
configurarla— y no revela dato alguno de la correspondencia.

## Paso 2. El disparador

**«Cuando llegue un correo electrónico nuevo (V3)»**, del conector Office 365
Outlook.

| Parámetro | Valor |
|---|---|
| Carpeta | La que vaya a vigilar |
| Incluir datos adjuntos | **Sí** |
| Solo con datos adjuntos | A su criterio |

Acote el disparador con una carpeta o una lista de remitentes. Clasificar todo
el buzón convierte las fichas en ruido, y una ficha que nadie lee no sirve de
nada.

## Paso 3. Filtrar los adjuntos

**«Filtrar matriz»** (operación de datos).

| Parámetro | Valor |
|---|---|
| Desde | `triggerOutputs()?['body/attachments']` |
| Condición | `endsWith(toLower(item()?['name']), '.pdf')` **es igual a** `true` |

Este paso no es imprescindible pero conviene: el correo institucional lleva el
logotipo de la entidad en la firma, y remitirlo gasta ancho de banda y tiempo
de espera sin provecho. El servidor, por su parte, ya descarta cuanto no sea
PDF y lo enuncia en `adjuntos_no_analizados` sin generar alerta de
ilegibilidad, de modo que omitir este filtro no produce alertas espurias: solo
desperdicia transferencia.

Se filtra por extensión y no por el indicador de contenido incorporado porque
la extensión está disponible de modo uniforme en el conector.

## Paso 4. Asignar los nombres de campo

**«Seleccionar»** (operación de datos).

| Parámetro | Valor |
|---|---|
| Desde | `body('Filtrar_matriz')` |
| Clave `nombre` | `item()?['name']` |
| Clave `contenido_base64` | `item()?['contentBytes']` |

El conector entrega el contenido del adjunto ya en base64, que es exactamente
lo que el endpoint espera.

## Paso 5. Llamar al endpoint

**«HTTP»**.

| Parámetro | Valor |
|---|---|
| Método | `POST` |
| URI | `https://<su-app>.up.railway.app/correo/triage/json` |
| Encabezados | `Content-Type: application/json` y `X-API-Key: <su clave>` |

Cuerpo:

```json
{
  "remitente": "@{triggerOutputs()?['body/from']}",
  "asunto": "@{triggerOutputs()?['body/subject']}",
  "cuerpo_base64": "@{base64(triggerOutputs()?['body/body'])}",
  "fecha_recepcion": "@{formatDateTime(triggerOutputs()?['body/receivedDateTime'], 'yyyy-MM-dd')}",
  "aplicar_ocr": true,
  "redactar": true,
  "adjuntos": @{body('Seleccionar')}
}
```

Dos detalles de esa plantilla merecen explicación.

**`cuerpo_base64` en lugar de `cuerpo`.** El cuerpo de un correo de Outlook es
HTML y contiene comillas dobles y saltos de línea. Insertarlo tal cual en una
plantilla JSON puede producir un JSON inválido, y el flujo fallaría con un
error que no señala su causa. El endpoint acepta el cuerpo en base64
precisamente para eliminar ese riesgo, y `base64()` es una función propia de
Power Automate. Si prefiere `cuerpo`, funciona cuando el valor se interpola
limpiamente, pero la variante codificada no depende de ello.

**`"adjuntos": @{body('Seleccionar')}` va sin comillas.** Debe insertarse como
arreglo, no como texto. Si lo rodea de comillas, el endpoint recibirá una
cadena y rechazará la solicitud.

### Ajustes de la acción

En el menú de la acción, «Configuración»:

- **Directiva de reintentos: Ninguna.** Si la llamada agota la espera, el
  reintento clasificaría el mismo correo otra vez: consumiría el modelo de
  nuevo y, si el reintento sí responde, usted recibiría la ficha duplicada. El
  endpoint no guarda estado y no puede descartar la repetición por su cuenta.
- **Tiempo de espera.** El límite de una llamada sincrónica es del orden de 120
  segundos; confirme el valor en esa misma pantalla. El reconocimiento óptico
  de un documento escaneado extenso puede acercarse a ese límite. Si lo alcanza,
  tiene tres salidas, de menor a mayor renuncia: reducir `DPI_OCR` a 200, que
  aproximadamente lo duplica en velocidad con poca pérdida en documentos
  mecanografiados; reducir `MAX_PAGINAS_OCR`; o remitir `aplicar_ocr: false`,
  que renuncia a leer los escaneados y es la salida menos recomendable, pues
  son justamente los documentos más relevantes.

## Paso 6. Remitir la ficha

**«Enviar un correo electrónico (V2)»**.

| Parámetro | Valor |
|---|---|
| Para | Su dirección institucional |
| Asunto | `@{body('HTTP')?['redaccion']?['asunto']}` |
| Cuerpo | `@{body('HTTP')?['redaccion']?['html']}` |
| Is HTML | **Sí** (en las opciones avanzadas) |

El endpoint devuelve la ficha ya redactada en `redaccion` —asunto, texto y
HTML— precisamente para que el flujo no deba componer el mensaje con
expresiones ni recorrer la lista de alertas. El HTML entrega el contenido
recibido ya escapado.

### Para recibir solo lo que importa

Si no quiere una ficha por cada correo, interponga una **«Condición»** antes de
enviar:

- `@{body('HTTP')?['urgencia']}` **no es igual a** `BAJA`, o bien
- `@{length(body('HTTP')?['alertas'])}` **es mayor que** `0`

La primera le remite solo lo urgente; la segunda, solo lo que tiene alguna
incongruencia. Conviene empezar sin condición durante una semana, para calibrar
con casos reales qué merece aviso.

### Para que un fallo no pase inadvertido

Agregue una acción de correo configurada con «Ejecutar después» → «Error» de la
acción HTTP, que le avise cuando la clasificación falle. De lo contrario el
flujo fallará en silencio y usted creerá que no llegó correspondencia.

## Qué devuelve el endpoint

La ficha completa está descrita en [triage-correo.md](triage-correo.md). Para
el flujo bastan cuatro campos:

| Campo | Uso |
|---|---|
| `redaccion.asunto` | Asunto del correo que se remite |
| `redaccion.html` | Cuerpo del correo que se remite |
| `urgencia` | `ALTA`, `MEDIA` o `BAJA`, para la condición |
| `alertas` | Arreglo de incongruencias, para la condición |

## Qué no pude verificar

No entrego un paquete importable de Power Automate. Construirlo exige empacar
una solución con sus conexiones, y no tengo forma de probar aquí que importe
correctamente en su tenant; un paquete que falla al importar cuesta más tiempo
que configurar cinco acciones. Los pasos de arriba sí están verificados del
lado del endpoint: las pruebas cubren la forma exacta de la solicitud que esta
plantilla produce, incluidos el cuerpo en base64, los adjuntos en base64 y los
adjuntos que no son PDF.

Los nombres de los parámetros del conector de Outlook y los límites de la
acción HTTP corresponden a lo que documenta Microsoft, pero esa interfaz cambia
con cierta frecuencia. Si un nombre no coincide, el valor equivalente aparece
en el panel de contenido dinámico del propio diseñador.

## Comparación con la ruta de reenvío

| | Power Automate | Reenvío a buzón propio |
|---|---|---|
| Sale correspondencia del tenant | No | Sí |
| Credenciales del buzón institucional | No se usan | No se usan |
| Requiere licencia premium | Sí | No |
| Requiere autorización institucional | No, si tiene la licencia | Sí, si el reenvío externo está bloqueado |
| Radicado remitido para el cotejo | No disponible | Declarable al reenviar a mano |
| Estado | Documentada aquí | Implementada en `ingesta/` |

Ninguna de las dos es superior en todo. Si tiene la licencia premium, esta ruta
es preferible por el tratamiento de la información. Si no la tiene, la de
reenvío funciona hoy.

## Sobre la información que circula

Esta ruta no envía correspondencia a un buzón externo, pero sí transmite el
contenido del correo y de sus adjuntos al proveedor del modelo de lenguaje. La
correspondencia puede contener información sujeta a reserva de la actuación
disciplinaria y datos personales protegidos por la Ley 1581 de 2012.

Acote el disparador a correspondencia administrativa, excluyendo los flujos de
expedientes. El endpoint, por su parte, no almacena el texto de los adjuntos:
lo usa en memoria y devuelve solo la ficha estructurada.
