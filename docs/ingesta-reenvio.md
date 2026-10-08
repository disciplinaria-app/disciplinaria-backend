# Ingesta por reenvío a un buzón propio

Esta es la ruta de ingesta que no depende del área técnica. Una regla del
correo institucional reenvía la correspondencia a un buzón propio del sistema;
un worker lo sondea, clasifica cada correo nuevo y remite la ficha.

El buzón institucional no se toca: el sistema nunca recibe sus credenciales.

## Lo primero que debe verificarse

**Exchange Online bloquea por defecto el reenvío automático hacia dominios
externos.** Es una configuración habitual en las políticas antispam de salida
de Microsoft 365, y si está activa en el tenant de la Rama Judicial, la regla
automática no entregará nada y el buzón quedará vacío sin mensaje de error
visible.

Verifíquelo antes de configurar lo demás: cree la regla, envíese un correo de
prueba con un PDF y confirme que llega al buzón propio. Si no llega, quedan dos
salidas:

1. **Reenvío manual.** Usted reenvía los correos que quiera clasificar. Es la
   salida inmediata, y además habilita las directivas que se describen más
   abajo, con las que el cotejo de radicados gana precisión.
2. **Solicitar la excepción** a la Dirección Ejecutiva de Administración
   Judicial para su buzón. Si va a pedir una autorización de todos modos,
   conviene comparar esta petición con la de la ruta de Power Automate, que es
   institucionalmente más defendible porque no envía correo fuera del tenant.

## Paso 1. Crear el buzón propio

Cualquier proveedor con IMAP sirve. Con Gmail:

1. Cree una cuenta destinada solo a esto.
2. Active la verificación en dos pasos.
3. Genere una **contraseña de aplicación** y úsela en `IMAP_CLAVE` y
   `SMTP_CLAVE`. La contraseña ordinaria de la cuenta no funciona.

## Paso 2. Crear la regla en Outlook

En el correo institucional, cree una regla que remita la correspondencia al
buzón propio.

**Prefiera «Redirigir» antes que «Reenviar».** La redirección conserva el
remitente original en el sobre del mensaje, de modo que el worker lo lee
directamente. El reenvío, en cambio, pone su propia dirección como remitente y
sepulta la del tercero dentro del cuerpo o en un adjunto `message/rfc822`; el
worker sabe desenvolver ambas formas, pero la redirección no depende de ello.

Acote la regla con un criterio: una carpeta, una lista de remitentes o los
correos con adjunto. Reenviar todo el buzón convierte las fichas en ruido, y
una ficha que nadie lee no sirve de nada.

Declare su dirección institucional en `DIRECCIONES_PROPIAS`. De ella depende
que el worker reconozca un reenvío: sin ese dato, el cotejo compararía la
entidad interpelada contra su propio despacho y nunca advertiría la
discrepancia.

## Paso 3. Configurar el worker

Las variables están enumeradas y comentadas en `.env.example`. Para una prueba
local:

```bash
cp .env.example .env    # y complete los valores
pip install -r requirements.txt
python -m ingesta.worker --una-vez
```

Si falta configuración, el worker lo enumera y termina con código 2 sin
intentar conectarse. Reenvíese un correo de prueba con un PDF y confirme que la
ficha llega.

## Paso 4. Desplegar

Dos formas, ambas sobre el mismo repositorio:

**Tarea programada (recomendada).** Un *cron job* de Railway que ejecute
`python -m ingesta.worker --una-vez` cada cinco o diez minutos. No mantiene un
proceso encendido y el costo es mínimo.

**Servicio permanente.** Un segundo servicio de Railway con el comando de
inicio `python -m ingesta.worker`, que sondea cada `INTERVALO_SONDEO` segundos.
El `Procfile` ya declara el proceso `worker` para esta forma. Conviene cuando se
quiere latencia baja.

En ambos casos el servicio necesita las mismas variables de entorno, incluida
`OPENROUTER_API_KEY`, y las dependencias de sistema del reconocimiento óptico
que instala `nixpacks.toml`.

## Directivas para el reenvío manual

Al reenviar a mano puede declarar el contexto del envío escribiendo al comienzo
del mensaje:

```
#entidad Fiduprevisora S.A.
#radicado CNDJ-2025-0412
#asunto Oficio CNDJ-2025-0412 — solicitud de información
```

Las tres son opcionales y se leen del cuerpo del reenvío, no del mensaje
original.

`#radicado` merece atención: **la entidad interpelada el sistema la deduce de
la cadena citada, pero el radicado que usted remitió no es deducible.** Sin
declararlo, el cotejo de radicados queda en `INDETERMINADO` y la ficha lo
informa. Un reenvío automático por regla no trae directivas, de modo que en esa
modalidad el cotejo descansa solo en la entidad.

## Qué hace el worker en cada ciclo

1. Consulta los mensajes no leídos del buzón, por UID y con `BODY.PEEK`, para
   no marcarlos como leídos por el solo hecho de descargarlos.
2. Lee cada mensaje: desenvuelve el reenvío si lo hay, convierte el HTML a
   texto, separa el mensaje nuevo de la cadena citada y recoge los adjuntos.
3. Clasifica con el triage en proceso, sin pasar por la API HTTP.
4. Remite la ficha y marca el correo como leído.

### Garantías del ciclo

- **Nada se pierde.** El correo se marca como leído solo cuando su
  procesamiento concluye. Una caída a mitad de ciclo lo deja pendiente para el
  siguiente.
- **Un correo no arrastra a los demás.** El fallo de uno no detiene el ciclo ni
  el worker; una caída de red solo espacia los reintentos.
- **Ningún fallo queda en silencio.** Agotados los reintentos
  (`MAX_INTENTOS_POR_CORREO`), se remite un aviso que identifica el correo y el
  motivo, y recién entonces se da por procesado. Y si tampoco se puede remitir
  ese aviso, el correo se conserva sin leer: darlo por procesado sin que usted
  lo sepa equivaldría a perder correspondencia.

### Por qué la ficha no se clasifica a sí misma

Por omisión `DESTINATARIO_FICHAS` es el propio buzón de ingesta, de modo que la
ficha volvería a él. El sistema marca cada ficha que remite con la cabecera
`X-Disciplinaria-Triage` y omite los mensajes que la llevan; sin esa
salvaguarda el ciclo se realimentaría sin término. Puede, por tanto, usar el
mismo buzón para la ingesta y para las fichas sin consecuencia alguna.

### Qué adjuntos se analizan

Solo los PDF. Los demás adjuntos reales se enuncian por su nombre en la ficha,
sin someterlos a extracción.

El contenido incorporado se descarta por completo. Casi todo correo
institucional lleva el logotipo de la entidad en la firma; tratarlo como
adjunto produciría una alerta de documento ilegible en cada mensaje, que es la
forma más rápida de que usted deje de leer las alertas.

Un PDF declarado como `application/octet-stream` —cosa frecuente— se reconoce
por su extensión o por su firma binaria.

## Límites conocidos de esta ruta

- **El radicado remitido no es deducible** en el reenvío automático. Véanse las
  directivas.
- **La fecha de la ficha es la del sobre**, no la de la línea «Enviado:» del
  bloque reenviado, cuyo formato en español no se interpreta de modo fiable.
  Con redirección ambas coinciden.
- **El registro de lo procesado es efímero en Railway** y se pierde al
  redesplegar. Es un resguardo secundario: lo que evita reprocesar es la marca
  de leído del propio buzón IMAP, que sí persiste.
- **Un mensaje MIME corrupto no se descarta.** El analizador de la biblioteca
  estándar es tolerante y produce un mensaje de encabezados vacíos; el worker lo
  clasifica y lo notifica igual, lo que es preferible a descartar
  correspondencia que podría ser legítima.

## Sobre la información que circula

Esta ruta hace salir correspondencia institucional hacia un buzón de proveedor
comercial y, desde allí, hacia un proveedor de modelos de lenguaje. La
correspondencia puede contener información sujeta a reserva de la actuación
disciplinaria y datos personales protegidos por la Ley 1581 de 2012.

Dos recomendaciones concretas: acote la regla de Outlook a correspondencia
administrativa, excluyendo los flujos de expedientes, y considere que la ruta
de Power Automate —que no envía correo fuera del tenant institucional— es
preferible en este aspecto si llega a estar disponible.

El sistema, por su parte, no almacena el texto de los adjuntos: lo usa en
memoria y entrega solo la ficha estructurada.
