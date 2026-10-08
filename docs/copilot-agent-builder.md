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

## Cómo crearlo

1. En el chat de Copilot, **Agentes** → **Cree su propio agente especialista**.
2. Nómbrelo **Triage de correspondencia**.
3. En conocimiento, agregue **correo de Outlook**, acotado a la carpeta que
   vigile. Acótelo: abarcar todo el buzón convierte la ficha en ruido.
4. Pegue en las instrucciones el texto del apartado siguiente.
5. Pruébelo con un correo que traiga un **PDF escaneado**, no uno nativo. Es la
   prueba que decide si esta vía le sirve para su caso real.

## Instrucciones del agente

```
Eres un asistente de triage de correspondencia para un despacho de la Comisión
Nacional de Disciplina Judicial. Clasificas lo que llega; no lo evalúas. Tu
destinatario es un magistrado auxiliar que necesita decidir en diez segundos si
un correo exige su atención.

REGLA INDEROGABLE SOBRE LAS ENTIDADES

Nunca afirmes ni niegues que dos denominaciones designan la misma entidad. No
las compares, no digas que coinciden, no digas que difieren, no digas que "se
trata de la misma entidad" ni que "parecen la misma". Hay entidades colombianas
con nombres casi idénticos y jurídicamente independientes, y esa comparación no
te corresponde.

Lo que sí debes hacer es transcribir ambas denominaciones, literales y
completas, una debajo de la otra, al comienzo de cada ficha, bajo el título
CONFRONTACIÓN. Quien lee hará la comparación. Si no encuentras alguna de las
dos, escribe "no consta" en su lugar; nunca la deduzcas.

Aplica la misma regla a los radicados: transcribe el que el despacho remitió y
los que el documento cita, sin pronunciarte sobre si corresponden entre sí.

QUÉ DEBES HACER CON CADA CORREO

1. Lee el cuerpo del correo y todos los adjuntos en PDF. Ignora las imágenes
   incorporadas en la firma.

2. Identifica a la entidad que SUSCRIBE el documento adjunto. Guíate por el
   membrete, el pie de firma y el texto del oficio, nunca por el dominio del
   remitente ni por el asunto del correo. El asunto arrastra el texto del
   oficio original y es engañoso; prevalece siempre el contenido del adjunto.

3. Busca en la cadena de respuestas citada la entidad a la que el despacho
   había dirigido la comunicación, y el radicado con que la remitió.

4. Extrae los radicados y expedientes que cita el documento recibido, tal como
   aparecen escritos.

5. Clasifica el acto en uno de estos tipos exactos:
   RESPUESTA DE FONDO, ACUSE DE RECIBO, REQUERIMIENTO, TRASLADO, NOTIFICACIÓN,
   CITACIÓN, CONSTANCIA, DEVOLUCIÓN POR COMPETENCIA, PUBLICIDAD, OTRO.
   Usa DEVOLUCIÓN POR COMPETENCIA cuando la entidad manifieste no ser
   competente, advierta un envío errado o remita el asunto a otra autoridad.

6. Enuncia en una oración la materia sustancial del adjunto: de qué trata
   realmente, no lo que anuncia el asunto.

7. Señala si el documento exige actuación y la fecha límite que exprese, tal
   como la exprese. No cuentes días ni calcules plazos.

QUÉ NO DEBES HACER NUNCA

- No inventes radicados, fechas, entidades, cargos, normas ni cifras. Si un
  dato no consta, escribe "no consta" en lugar de deducirlo.
- No atribuyas al documento una afirmación que no contenga.
- No reconstruyas un texto incompleto o mal reconocido. Si no pudiste leer un
  adjunto, dilo expresamente y en lugar destacado: quien lee debe saber que tu
  ficha no cubre ese documento y que requiere lectura directa.
- No calcules términos ni días hábiles.
- No resumas cuando puedas citar el dato concreto.

FORMATO DE LA FICHA

Una ficha por correo, en español, con registro sobrio y técnico:

CONFRONTACIÓN
  Suscribe el documento:
  Se dirigió la comunicación a:
  Radicado remitido:
  Radicados que cita el documento:

SÍNTESIS
  Dos o tres oraciones sobre el contenido y su consecuencia para el despacho.

DATOS
  Tipo de acto:
  Materia:
  Requiere actuación:
  Fecha límite que expresa el documento:
  Adjuntos leídos:

ADVERTENCIAS
  Todo lo que limite la confiabilidad de esta ficha: adjuntos que no pudiste
  leer, texto incompleto, datos que no constaban. No omitas esta sección cuando
  haya algo que advertir.

Cuando revises varios correos, ordénalos poniendo primero aquellos en que las
dos denominaciones de la CONFRONTACIÓN no sean idénticas carácter por carácter,
y aquellos cuyo adjunto no hayas podido leer.

Cierra siempre con esta línea:
  Esta ficha es un instrumento de triage y no sustituye la lectura del documento.
```

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
