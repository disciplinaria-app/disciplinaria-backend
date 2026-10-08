# Agente en Agent Builder (incluido en su licencia)

La pantalla «Cree su propio agente especialista» del chat de Copilot es **Agent
Builder**, que no es Copilot Studio. La distinción decide el costo y el alcance.

## Lo que esto confirma

**Está incluido en su licencia.** La documentación de Microsoft lo dice sin
rodeos: «Agents you build with the Agent Builder feature in Microsoft 365
Copilot are included in your Microsoft 365 Copilot license», con la salvedad de
que «these agents feature functionality that is a subset of what Microsoft 365
Copilot supports». Ningún crédito, ninguna suscripción de Azure, ninguna
decisión del administrador del tenant.

**Puede leer su correo.** Entre las fuentes de conocimiento admitidas figura el
correo de Outlook, junto con sitios de SharePoint, chats de Teams y direcciones
web públicas. El acceso puede acotarse a carpetas determinadas.

**No puede llamar a servicios externos.** Esta es la limitación decisiva:
«Agent Builder doesn't support authoring actions that integrate external
services. To add low-code actions, connectors, or workflows, copy the agent to
Microsoft Copilot Studio.» Por tanto **el agente no puede invocar
`/correo/cotejo`**, y el cotejo determinista no está disponible por esta vía.

**No se dispara solo.** Agent Builder produce agentes declarativos, que
responden cuando usted los invoca. El disparo por la llegada de un correo
pertenece a Copilot Studio, y ahí reaparecen los créditos y la suscripción de
Azure.

## La adaptación que esto exige

Sin cotejo determinista, la tentación sería pedirle al agente que compare las
entidades. Es justamente lo que no debe hacerse: un modelo acierta casi siempre
al decidir si «La Previsora S.A.» y «Fiduprevisora S.A.» son la misma entidad,
y «casi siempre» no sirve cuando el error consiste en no advertir que la
respuesta vino de otra entidad.

La solución es no pedirle ese juicio. **Se le prohíbe comparar y se le ordena
exhibir**: que transcriba, una debajo de la otra y al comienzo de la ficha, la
denominación de quien suscribe el documento y la de la entidad a la que se
dirigió la comunicación, ambas literales. La comparación la hace usted, de un
vistazo, y no depende de que el modelo la acierte.

Es una degradación honesta: se convierte un juicio poco fiable del modelo en
una tarea de transcripción, que sí cumple con fiabilidad.

## Ficha de creación

En el chat de Copilot: **Agentes** → **Cree su propio agente especialista**. El
cuadro «Generador de agentes de mensajes» construye el agente conversando; **no
lo use para esto**. Pase a la pestaña de configuración manual y complete los
campos uno a uno: una descripción conversacional produce instrucciones vagas, y
aquí lo que importa es precisamente lo que las instrucciones prohíben.

### Nombre

```
Triage de correspondencia
```

### Descripción

```
Clasifica la correspondencia recibida con adjuntos en PDF y entrega una ficha por correo: quién suscribe el documento, de qué trata realmente, qué actuación exige y qué incongruencias presenta frente a lo que el despacho había remitido.
```

### Instrucciones

El texto íntegro está en [`copilot/instrucciones-agente.txt`](copilot/instrucciones-agente.txt),
listo para copiar sin formato. Son 4.798 caracteres.

### Conocimiento

Agregue **correo de Outlook** como fuente, acotado a la carpeta que vigile. No
agregue sitios de SharePoint ni búsqueda web: no aportan a esta tarea y la
búsqueda web puede inducir al agente a completar datos con material ajeno al
documento, que es justamente lo que las instrucciones le prohíben.

### Iniciadores de conversación

```
Revisa la correspondencia recibida hoy
Entrégame una ficha por cada correo con adjunto de esta semana
Revisa los correos de los últimos tres días que traigan PDF
Para el último correo con adjunto: transcribe el membrete y quién firma
```

El cuarto no es de uso diario: es el que sirve para comprobar si el agente leyó
de verdad el documento.

## Protocolo de prueba del PDF escaneado

Es la prueba que decide si esta vía le sirve. Hay que hacerla con cuidado,
porque el modo de fallar más probable no es que el agente diga «no pude leerlo»,
sino que **describa el documento a partir del asunto del correo y del nombre del
archivo**, produciendo una ficha verosímil y hueca.

### Separe los dos posibles fallos

Son fallos distintos y conviene no confundirlos:

1. **Que Copilot no sepa leer PDF escaneados.** Pruébelo aparte: en un chat
   ordinario de Copilot, sin el agente, adjunte el PDF escaneado directamente y
   pídale que transcriba el membrete y el pie de firma. Si aquí falla, ninguna
   configuración del agente lo arreglará.
2. **Que el agente no alcance el adjunto desde el buzón.** Si la prueba 1
   funciona pero el agente no, el problema está en el alcance de la fuente de
   conocimiento, no en la lectura.

### Cómo saber si leyó de verdad

Pídale un dato que solo exista dentro de la imagen del documento y que no pueda
inferirse del correo:

```
Del último correo con adjunto: transcribe literalmente la primera línea del
membrete, y el nombre y el cargo de quien suscribe.
```

Después abra el PDF y coteje carácter por carácter. Tres desenlaces:

- **Transcribe bien** → lo leyó. La vía sirve.
- **Dice que no pudo leerlo** → no lo leyó, pero se comportó como debía. Es el
  fallo honesto, y confirma que necesita el reconocimiento óptico del backend.
- **Responde algo verosímil que no coincide con el documento** → es el desenlace
  peligroso: inventó. Si ocurre, esta vía no es utilizable para correspondencia
  disciplinaria, por bien que funcione en los demás casos.

### Dos precauciones

**No pruebe con un correo recién llegado.** El acceso al buzón se apoya en el
índice de búsqueda, que puede no haber alcanzado un mensaje de hace minutos.
Use uno de hace unos días para que un fallo de indexación no se confunda con un
fallo de lectura.

**Pruebe con un escaneado de verdad.** Un PDF generado desde Word tiene capa de
texto y se lee sin dificultad; no prueba nada. Necesita un oficio firmado y
digitalizado, de los que motivaron todo esto.

## Resultado de la primera prueba

Sobre una notificación judicial de diez páginas, con la pregunta de
transcripción del membrete:

**Lo que funcionó.** Transcribió correctamente la primera línea del membrete, de
modo que leyó el contenido y no lo dedujo del asunto ni del nombre del archivo.
Al no hallar la firma escribió «no consta» en lugar de inventar un nombre y un
cargo: la regla que más importaba se sostuvo. Citó la fuente de cada dato. Al
pedírsele el detalle, enumeró las diez páginas una por una y declaró
expresamente su limitación.

**Lo que quedó abierto.** Dijo que la firma «no quedó capturada en el texto
extraído» y que «no aparece en la extracción disponible del PDF». Esa redacción
sugiere que trabaja sobre la capa de texto del documento. De ahí no se sigue
todavía si aplica reconocimiento óptico: depende de si ese documento tenía firma
visible como imagen —en cuyo caso no la reconoció— o si carecía de firma
impresa por estar suscrito con certificado digital, como es frecuente en las
notificaciones judiciales electrónicas. Se resuelve mirando el pie de la última
página del texto principal.

**Lo que enseñó sobre el material.** Ocho de las diez páginas eran constancias
de retransmisión y de entrega de Outlook. Es lo habitual en estas
notificaciones, e inflaba la ficha sin aportar nada. De ahí salieron las dos
reglas que las instrucciones incorporan ahora: no describir ni contar esas
constancias entre los adjuntos leídos, y consignar expresamente cuándo un
documento termina en fórmula de despedida sin firma visible, sin suponer quién
lo suscribe ni dar por sentado que falta una página.

## Cómo usarlo

Invóquelo una vez al día: «Revisa la correspondencia recibida hoy y entrégame
una ficha por cada correo con adjunto.»

No sustituye al aviso automático —usted debe acordarse de preguntar—, pero
cubre el caso que lo motivó: la ficha le habría puesto «La Previsora S.A.»
encima de «Fiduprevisora S.A.» en las dos primeras líneas, y el error habría
saltado sin necesidad de abrir el PDF.

## Lo que esta vía no da

| | Agent Builder | Copilot Studio | Backend propio |
|---|---|---|---|
| Costo adicional | Ninguno | Créditos y Azure | Consumo del modelo |
| La correspondencia sale del tenant | No | No, salvo el cotejo | Sí |
| Aviso automático al llegar | No | Sí | Sí |
| Cotejo determinista | No | Sí, por el endpoint | Sí |
| Cómputo de términos | No | No | Sí |
| Lee PDF escaneados | Por verificar | Por verificar | Sí, con OCR |
| Disponible | Hoy | Tras licenciamiento | Implementado |

**Mi recomendación:** cree este agente ahora, porque no cuesta nada y cubre
buena parte de la necesidad desde hoy. Úselo una o dos semanas con
correspondencia real. De esa prueba saldrán dos respuestas que ninguna
documentación le dará: si Copilot lee sus PDF escaneados, y si el aviso
automático le hace falta lo bastante como para justificar los créditos o la
ruta de reenvío.
