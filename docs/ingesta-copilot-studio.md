# Ingesta con un agente de Copilot Studio

Un agente que se dispare solo al llegar un correo, dentro del tenant
institucional. Es la ruta con mejor tratamiento de la información y la de
licenciamiento más incierto.

Este documento reúne lo que pude verificar, lo que no, el diseño que propongo y
lo que esa elección cuesta.

## Estado de la verificación

La política de red de este entorno permite `www.microsoft.com` pero **bloquea
`learn.microsoft.com`, `azure.microsoft.com`, `adoption.microsoft.com`,
`techcommunity.microsoft.com` y `microsoft.github.io`**. Con lo alcanzable se
pudo confirmar la estructura de precios y el alcance de la licencia en las
propias páginas de Microsoft; **la tabla de tarifas por acción reside en
`learn.microsoft.com` y no pudo consultarse**.

Cada afirmación de abajo indica su respaldo. Habilitar `learn.microsoft.com` y
`azure.microsoft.com` en la configuración de red del entorno permitiría cerrar
el punto que queda abierto.

### Confirmado en páginas de Microsoft

De [Microsoft Copilot Studio](https://www.microsoft.com/en-us/microsoft-365-copilot/microsoft-copilot-studio)
y [Copilot Studio Plans and Pricing](https://www.microsoft.com/en-us/microsoft-365-copilot/pricing/copilot-studio):

- **Precio de la capacidad.** «Copilot Studio is sold as tenant-wide Copilot
  Credit packs of 25,000 Copilot Credits each, priced at $200.00/pack/month.»
  Esto fija el crédito en **0,008 dólares**. Existe también una modalidad de
  pago por consumo, sin diferencia funcional: «There are no in-product features
  or capability differences between the Copilot Credit pack and the
  pay-as-you-go meter.»
- **Qué consume créditos.** «Whenever an action or response is completed by an
  agent, a varying number of Copilot Credits will be billed.» Es decir, cada
  acción o respuesta que el agente complete, en cantidad variable.
- **Qué cubre la licencia que usted tiene.** «For those licensed for Microsoft
  365 Copilot, usage of agents **published to Microsoft 365 Copilot** is
  included in their license.» La licencia da acceso a construir y usar agentes
  internos «within Microsoft 365 using the Copilot Chat and Standard harness».
- **Requisito que no figuraba en el diseño inicial:** «An Azure subscription is
  required to use agents.» La modalidad de pago por consumo exige además una
  suscripción de Azure vinculada al entorno.

### Agent Builder, que sí está incluido

Conviene no confundir dos productos. **Agent Builder** —la pantalla «Cree su
propio agente especialista» del chat de Copilot— produce agentes declarativos y
está incluido en la licencia: «Agents you build with the Agent Builder feature
in Microsoft 365 Copilot are included in your Microsoft 365 Copilot license»,
con funcionalidad que es «a subset of what Microsoft 365 Copilot supports».
Admite el correo de Outlook como fuente de conocimiento.

Pero **no admite acciones hacia servicios externos**: «Agent Builder doesn't
support authoring actions that integrate external services. To add low-code
actions, connectors, or workflows, copy the agent to Microsoft Copilot Studio.»
De modo que un agente de Agent Builder no puede invocar `/correo/cotejo`, y
tampoco se dispara solo.

Esa vía, con la adaptación que su limitación exige, está documentada en
[copilot-agent-builder.md](copilot-agent-builder.md). Es la única que no cuesta
nada y está disponible hoy.

### Lo que no pudo confirmarse en documentación formal

**Si una ejecución disparada por evento queda cubierta por la licencia de
Microsoft 365 Copilot.** Las páginas de producto alcanzables no lo dicen, y la
tabla de tarifas por acción está en `learn.microsoft.com`, bloqueado.

Lo que sí hay, concordante y de dos fuentes distintas: una respuesta de un
moderador identificado como empleado de Microsoft en el foro de preguntas de
Learn, según la cual las interacciones iniciadas por un usuario licenciado
dentro de Microsoft 365 quedan incluidas, mientras que «autonomous or unattended
executions, such as scheduled runs, Power Automate triggers, or background
tasks, always consume credits regardless of licensing»; y el material de
capacitación Agent Academy de Microsoft, que enuncia la misma regla práctica.
Ninguna de las dos es documentación normativa.

Concuerda además con la redacción de la página de precios, que cubre los
agentes *publicados en* Microsoft 365 Copilot, esto es, consumidos por un
usuario licenciado a través de esa superficie. Un agente que se dispara por la
llegada de un correo no está siendo usado por nadie allí: corre por su cuenta.

**Puede darse por probable, pero debe confirmarse con el representante de
licenciamiento antes de comprometer presupuesto.** La cifra de 25 créditos por
disparo sigue proviniendo solo de guías de terceros.

### Qué costaría, con lo que sí está confirmado

El precio del crédito está confirmado en 0,008 dólares; lo que falta es cuántos
créditos consume una ejecución. Con las cifras de terceros —45 créditos por
correo— el costo rondaría los **0,36 dólares por correo**, esto es, unos
**150 dólares mensuales** para veinte correos diarios en días hábiles.

Si la lectura de arriba fuese equivocada y las ejecuciones disparadas quedaran
cubiertas por la licencia, el costo tendería a cero. La diferencia entre ambos
escenarios es lo que hace indispensable la confirmación.

### Dos obstáculos institucionales

**La suscripción de Azure.** Está confirmado que se requiere para usar agentes.
Para la Rama Judicial no es activar una casilla: es una gestión de contratación
ante el área competente. Conviene medirla antes de avanzar en el diseño.

**La capacidad es de tenant, no de usuario.** Los paquetes de créditos se
compran a nivel de tenant, de modo que esto no se resuelve con su licencia
individual: requiere una decisión de quien administra el tenant institucional.

## Lo que sí está confirmado del patrón técnico

**El patrón existe y Microsoft lo documenta.** Un agente de Copilot Studio
admite un disparador «Cuando llegue un correo electrónico nuevo (V3)» del
conector Office 365 Outlook, configurado en la pestaña de activadores del
propio agente, sin necesidad de un flujo intermedio de Power Automate. Existe
también la variante para buzón compartido.

**Microsoft resuelve el mismo problema de los logotipos.** Su laboratorio
Agent Academy comprueba el tipo de contenido del adjunto antes de procesarlo,
para que solo se traten los PDF y se omitan las imágenes de las firmas. Es el
mismo cuidado que el backend aplica y confirma que el problema es real.

## Lo que depende de condiciones que debe verificar

**La orquestación generativa debe estar activa.** Una guía de enero de 2025
señala además que el idioma del agente debía estar en inglés para habilitar
esa funcionalidad. Si esa restricción sigue vigente, conviene comprobar que un
agente en inglés admita instrucciones y produzca respuestas en español, que es
lo que usted necesita.

**El estado del disparador por evento.** Las fuentes discrepan: alguna lo
describe como característica en versión preliminar y otra lo da por disponible
de modo general. Verifíquelo en su tenant.

## La tensión de fondo

Copilot Studio y el backend resuelven mitades que no se superponen, y conviene
verlo con claridad antes de elegir:

- **Copilot mantiene la correspondencia dentro del tenant.** Es la ventaja
  decisiva y la única razón de peso para preferir esta ruta.
- **Copilot no puede hacer el cotejo determinista.** Preguntarle a un modelo si
  «La Previsora S.A.» y «Fiduprevisora S.A.» son la misma entidad es
  exactamente la operación que no ofrece garantías. El cotejo del backend
  compara núcleos léxicos completos y nunca por subcadenas, con una prueba
  dedicada a ese caso. Un modelo acierta casi siempre, y «casi siempre» no es
  el criterio con que se decide si una respuesta corresponde a la actuación.

Elegir Copilot a secas obliga a renunciar al cotejo. Elegir el backend a secas
obliga a que la correspondencia salga del tenant.

## El diseño que propongo

Un agente que lea dentro del tenant y delegue solo la verificación.

```
Correo llega al buzón institucional
        │
        ▼
Agente de Copilot Studio (dentro del tenant)
        │  lee el cuerpo y el PDF adjunto
        │  identifica quién suscribe, el tipo de acto y la materia
        │  extrae los radicados citados
        ▼
Herramienta «Cotejar correspondencia» ──► POST /correo/cotejo
        │                                   sin modelo de lenguaje
        │  ◄── veredicto y alertas          sin contenido documental
        ▼
Agente redacta la ficha y la remite por correo
```

Lo único que sale del tenant son cuatro datos: la denominación de la entidad
interpelada, la de la entidad que suscribe, el radicado remitido y los
radicados hallados. **No sale el cuerpo del correo ni el texto de los
adjuntos.**

A cambio, se conserva la pieza que un modelo no resuelve con fiabilidad. El
endpoint no invoca al modelo, no recibe contenido documental —su esquema no
tiene campo para él— y opera aunque la clave del modelo no esté configurada.
Las pruebas verifican esas tres garantías, no solo el resultado.

### El endpoint

`POST /correo/cotejo`, con la misma clave de acceso en `X-API-Key`.

Solicitud:

```json
{
  "entidad_interpelada": "Fiduprevisora S.A.",
  "entidad_remitente": "La Previsora S.A. Compañía de Seguros",
  "radicado_enviado": "CNDJ-2025-0412",
  "radicados_hallados": ["CNDJ-2025-0412"]
}
```

Respuesta:

```json
{
  "cotejo": {
    "entidad_estado": "DIFIERE",
    "radicado_estado": "COINCIDE",
    "...": "..."
  },
  "alertas": [
    {"codigo": "ENTIDAD_DISTINTA", "severidad": "ALTA", "origen": "COTEJO", "descripcion": "..."}
  ],
  "veredicto": "La entidad que suscribe el documento NO es aquella a la que se dirigió la comunicación. Verifique si hubo confusión de destinatario. El radicado remitido sí figura citado en el documento."
}
```

El campo `veredicto` está redactado para que el agente lo reproduzca sin
reinterpretarlo. Es deliberado: el hallazgo que importa es justamente el que un
modelo tiende a suavizar.

## Configuración del agente

1. **Crear el agente** en Copilot Studio y activar la orquestación generativa.

2. **Pegar las instrucciones** de
   [copilot-studio-instrucciones.md](copilot-studio-instrucciones.md) en el
   campo de instrucciones.

3. **Agregar la herramienta.** Una herramienta desde una API REST, apuntando a
   `POST /correo/cotejo`, con la clave en `X-API-Key`. La documentación de
   Microsoft indica que la definición debe ser OpenAPI v2: una v3 se traduce
   automáticamente. La especificación de la API está en `/openapi.json` del
   servicio. Esa funcionalidad figura como versión preliminar, de modo que la
   alternativa, si no funciona, es exponer el endpoint mediante un flujo de
   Power Automate usado como herramienta.

   Nombre la herramienta **Cotejar correspondencia**, tal como la mencionan las
   instrucciones, y describa su propósito así: «Verifica de modo determinista
   si dos denominaciones designan la misma entidad y si dos citas designan el
   mismo radicado. Debe invocarse siempre; su veredicto no se reinterpreta.»

4. **Agregar el disparador** en la pestaña de activadores: «Cuando llegue un
   correo electrónico nuevo (V3)», con la carpeta y el filtro de remitentes que
   convenga. Acótelo: clasificar todo el buzón convierte las fichas en ruido.

5. **Agregar la acción de correo** que remita la ficha a su dirección.

6. **Probar con un PDF escaneado**, no con uno nativo. Es la prueba decisiva, y
   va explicada abajo.

## Las dos pruebas que deciden

**1. ¿El agente lee un PDF escaneado?** Su caso real fue un oficio firmado y
digitalizado, sin capa de texto. Si el agente no lo lee, no resuelve el
problema que usted tiene, por bien configurado que esté. El backend aplica
reconocimiento óptico precisamente por eso. No encontré fuente que lo confirme
ni lo descarte, así que hay que probarlo.

**2. ¿Cuánto consume una ejecución?** Es lo único que falta para cerrar el
cálculo: el precio del crédito está confirmado, no así cuántos créditos gasta
un disparo. Deje el agente corriendo un día con volumen real y lea el consumo.

## Límites de esta ruta

- **Lo que el backend garantiza por programa, aquí depende de instrucciones.**
  El catálogo cerrado de tipos y alertas, el descarte de lo que no pertenece a
  él, el cómputo de días en código: nada de eso es exigible a un agente
  gobernado por lenguaje natural. Puede desatender una instrucción.
- **El cómputo de términos se pierde.** Las instrucciones le prohíben al agente
  contar días, porque contarlos mal es peor que no contarlos. La ficha dirá la
  fecha que el documento expresa, y usted contará.
- **No hay traza del procesamiento.** El backend informa, documento por
  documento, si el texto se obtuvo de la capa nativa o por reconocimiento
  óptico, y cuántas páginas procesó. El agente no.
- **El radicado remitido sigue sin ser deducible**, igual que en la ruta de
  reenvío automático, salvo que conste en la cadena citada.

## Comparación de las tres rutas

| | Copilot Studio | Power Automate | Reenvío a buzón propio |
|---|---|---|---|
| La correspondencia sale del tenant | No | Sí, al endpoint | Sí, a un buzón externo |
| Cotejo determinista | Sí, por el endpoint de cotejo | Sí, completo | Sí, completo |
| Cómputo de términos en código | No | Sí | Sí |
| Traza de la extracción | No | Sí | Sí |
| Lee PDF escaneados | Por verificar | Sí, con OCR | Sí, con OCR |
| Licencia adicional | Créditos de Copilot y suscripción de Azure | HTTP premium | Ninguna |
| Costo por correo | ~0,36 USD (crédito confirmado, consumo estimado) | Consumo del modelo | Consumo del modelo |
| Estado | Diseñada; endpoint listo | Documentada; endpoint listo | Implementada y probada |

Ninguna domina a las demás. Si el tratamiento de la información pesa más que
las garantías de procesamiento y el costo es aceptable, esta ruta es la
indicada. Si pesan más las garantías, la de Power Automate conserva el
procesamiento íntegro sin sacar correspondencia a un buzón externo.
