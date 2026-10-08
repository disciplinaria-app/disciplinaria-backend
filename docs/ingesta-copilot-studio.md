# Ingesta con un agente de Copilot Studio

Un agente que se dispare solo al llegar un correo, dentro del tenant
institucional. Es la ruta con mejor tratamiento de la información y la de
licenciamiento más incierto.

Este documento reúne lo que pude verificar, lo que no, el diseño que propongo y
lo que esa elección cuesta.

## Advertencia sobre las fuentes

**La política de red de este contenedor bloquea `learn.microsoft.com`,
`adoption.microsoft.com` y `microsoft.github.io`**, de modo que no pude leer la
documentación primaria de Microsoft. Lo que sigue se apoya en resultados de
búsqueda —que sí citan textualmente páginas de Microsoft Learn— y en guías de
terceros que en varios puntos se contradicen entre sí.

Cada afirmación de abajo indica su grado de respaldo. Las que tocan
licenciamiento y costo deben confirmarse con el área de tecnología o con el
representante de licenciamiento antes de comprometerse.

Si quiere que verifique contra las páginas de Microsoft, puede habilitar esos
dominios en la configuración de red del entorno.

## Lo que sí está confirmado

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
lo que usted necesita. Es la primera prueba que haría.

**El estado del disparador por evento.** Las fuentes discrepan: alguna lo
describe como característica en versión preliminar y otra lo da por disponible
de modo general. Verifíquelo en su tenant.

## El dato que cambia la decisión

**Las ejecuciones autónomas se facturan en créditos de Copilot aunque el
usuario tenga licencia de Microsoft 365 Copilot.**

La licencia que usted tiene cubre el uso *interactivo* de agentes —preguntarle
algo a Copilot, como en la pantalla que me mostró—. Un agente que se dispara
solo, sin que nadie escriba, es una ejecución autónoma, y las guías coinciden
en que esa modalidad consume créditos de pago para cualquier licencia.

Las cifras provienen de guías de terceros, no de una página de Microsoft que
yo haya podido leer, y difieren entre sí:

| Concepto | Cifra citada |
|---|---|
| Disparador autónomo | ~25 créditos por ejecución |
| Acción del agente (llamada a conector) | ~5 créditos |
| Paquete prepagado | ~200 USD por 25.000 créditos mensuales |
| Pago por consumo | ~0,01 USD por crédito |

Una ejecución con cuatro acciones rondaría los 45 créditos, esto es, del orden
de **0,35 a 0,45 dólares por correo**. Veinte correos diarios en días hábiles
se acercarían a **160–200 dólares mensuales**.

No comparo esa cifra con el costo actual del backend porque no he verificado
las tarifas vigentes del modelo que usa; usted puede leer el gasto real en su
panel de OpenRouter y contrastarlo. Lo que sí puedo afirmar es que la
diferencia no es marginal, y que Microsoft publica un «Agent Usage Estimator»
para estimar lo propio antes de comprometerse.

**Esta es la comprobación que haría antes que ninguna otra**, porque si el costo
no resulta aceptable, el resto del diseño es ocioso.

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

**2. ¿Cuánto cuesta una ejecución?** Deje el agente corriendo un día con un
volumen real y lea el consumo de créditos. Las cifras de arriba son
estimaciones de terceros.

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
| Licencia adicional | Créditos de Copilot | HTTP premium | Ninguna |
| Costo por correo | ~0,35–0,45 USD (estimado) | Consumo del modelo | Consumo del modelo |
| Estado | Diseñada; endpoint listo | Documentada; endpoint listo | Implementada y probada |

Ninguna domina a las demás. Si el tratamiento de la información pesa más que
las garantías de procesamiento y el costo es aceptable, esta ruta es la
indicada. Si pesan más las garantías, la de Power Automate conserva el
procesamiento íntegro sin sacar correspondencia a un buzón externo.
