# Búsqueda jurisprudencial oficial — arquitectura multicanal

Fecha de contraste externo: 28 de septiembre de 2026.

## Objetivo

Aumentar de forma deliberada la capacidad de localizar jurisprudencia en los portales oficiales de la Corte Constitucional, Corte Suprema de Justicia, Consejo de Estado y Comisión Nacional de Disciplina Judicial. No depender de una sola caja de búsqueda ni de un solo mecanismo de acceso.

La búsqueda y la verificación son operaciones distintas. Una herramienta auxiliar puede descubrir una providencia; solo la fuente oficial permite confirmar sus datos y el pasaje utilizado en la providencia.

## Principio de búsqueda multicanal

Para cada cuestión jurisprudencial ejecutar, según necesidad, varias rutas complementarias. No abandonar una búsqueda porque falle la primera.

### Canal 0 — corpus oficial previamente verificado

Consultar primero el corpus/caché de textos oficiales ya recuperados. Reutilizarlo para localizar números, radicados, frases y citas relacionadas, pero comprobar fecha de recuperación y ejecutar búsqueda de actualización cuando la cuestión pueda haber evolucionado.

### Canal 1 — HTTP directo al portal oficial

Intentar consulta y recuperación con HTTP cuando el portal exponga resultados o documentos sin interacción compleja. Registrar URL inicial, URL final, código de respuesta, fecha, hash y método de adquisición.

### Canal 2 — buscador propio de la relatoría

Usar los campos y operadores del portal: número de providencia, radicado, texto completo, tema, fuente formal, ponente y rango temporal según la corporación. Generar variantes de consulta con frase exacta, términos nucleares, sinónimos jurídicos y combinación de conceptos.

### Canal 3 — Playwright sobre la relatoría oficial

Escalar a navegador cuando haya JavaScript, JSF, estado de sesión, paginación dinámica, formularios complejos, descargas generadas por interacción o resultados no accesibles por HTTP simple.

En un entorno de agente de programación, `lackeyjb/playwright-skill` puede aumentar directamente la capacidad del agente para explorar y automatizar esos portales. En producción dentro de Word, implementar la misma capacidad en `redactar2-mcp` mediante Playwright de servidor o un Playwright MCP interno realmente conectado. No suponer que una skill local de Playwright existe dentro de Word.

### Canal 4 — descubrimiento web restringido a dominios oficiales

Cuando el buscador interno sea pobre, usar búsqueda web con restricciones `site:` o APIs de búsqueda para descubrir URLs oficiales. Limitar preferentemente a dominios de la corporación y formular consultas por número, radicado, frase de ratio, término técnico y sentencia citada. El resultado sigue siendo candidato no verificado hasta leer la fuente oficial.

### Canal 5 — expansión Hyperresearch sobre fuentes oficiales

Usar los patrones de `jordan-gibbs/hyperresearch` para ampliar cobertura, no para sustituir la jerarquía jurídica:

- descomponer la pregunta en subreglas atómicas;
- ejecutar una búsqueda de amplitud con múltiples formulaciones;
- seguir las citas contenidas en las providencias encontradas;
- construir un grafo de contradicciones o tensiones;
- preguntar qué fuente podría derrotar la tesis provisional;
- ejecutar búsquedas de huecos identificados por el crítico;
- mantener un manifiesto reanudable y procedencia por fuente;
- verificar la unión afirmación-cita antes del cierre.

Cuando Hyperresearch se ejecute directamente en Claude Code/Codex, configurar la investigación jurídica para priorizar y, en la fase decisiva, restringir las fuentes a los dominios oficiales. Cuando no esté disponible dentro de Word, trasladar sus patrones de amplitud, profundidad, contradicción, persistencia y cite-check al orquestador del MCP.

### Canal 6 — verificación final en texto oficial

Todo precedente que vaya a sustentar la providencia debe volver a la fuente oficial. Confirmar identidad, mayoría, pasaje, contexto, problema decidido, regla, decisión y eventual voto separado. Ningún resultado de Google/Bing, Firecrawl, Hyperresearch, resumen automático, boletín no oficial o índice externo sustituye este paso.

## Estrategia por corporación

### Corte Constitucional

Punto prioritario: `https://www.corteconstitucional.gov.co/relatoria/`.

El buscador oficial admite búsqueda por texto completo, temas/subtemas, número de providencia y normas, además de rangos de fechas y restricciones textuales. Usar frases cortas y variantes; combinar número exacto y texto cuando se conozca. Si una ruta histórica redirige, seguir la ruta oficial vigente y registrar el cambio.

Orden sugerido: número exacto → frase exacta de la subregla → términos nucleares → tema/subtema → norma → seguimiento de sentencias citadas → actualización reciente.

### Corte Suprema de Justicia

Puntos prioritarios: sistema de consulta jurisprudencial y relatorías por Sala. Identificar primero especialidad: Civil/Agraria/Rural, Laboral, Penal, o Tutelas/Sala Plena. Aprovechar búsqueda por texto completo, magistrado, fecha, tipo de providencia, fuente formal y consultas combinadas cuando estén disponibles.

Orden sugerido: identificador/radicado → Sala competente → texto completo → fuente formal/tema → explorador de documentos → citas internas y providencias relacionadas.

### Consejo de Estado

Punto prioritario: Biblioteca Digital de SAMAI y su buscador de jurisprudencia. No confundir consulta del proceso con búsqueda jurisprudencial. Identificar Sección/Subsección cuando sea pertinente y usar radicado, fecha, tema, descriptor y texto.

Orden sugerido: radicado/identificador → Sección → frase técnica → tema → cita de precedente de unificación → seguimiento de providencias posteriores que la invoquen.

### Comisión Nacional de Disciplina Judicial

Punto prioritario: `https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml`.

El portal expone criterios como tipo de providencia, salvamento/aclaración, tema, ponente, fecha y texto completo. Por su naturaleza JSF, preparar un adaptador específico capaz de manejar estado de formulario, paginación y descarga; Playwright es un fallback especialmente relevante aquí.

Orden sugerido: radicado/ponente/fecha si se conocen → frase exacta de la falta o subregla → tema → texto completo → seguimiento de providencias citadas → búsqueda sobre la ventana de actualización (cuatro años anteriores a la fecha de corte). Para la línea anterior a la entrada en funcionamiento de la CNDJ (2021), buscar en la relatoría de la Sala Jurisdiccional Disciplinaria del Consejo Superior de la Judicatura.

## Generador de consultas

Para cada subregla producir al menos estas familias, sin nombres de partes del expediente:

1. **Identificador:** sentencia, auto, radicado, ponente conocido.
2. **Ratio:** frase técnica breve entre comillas y una versión sin comillas.
3. **Categoría dogmática:** institución + régimen + corporación.
4. **Problema aplicado:** categoría + consecuencia jurídica buscada.
5. **Actualización:** misma subregla + los cuatro años anteriores a la fecha de corte, calculados en cada ejecución.
6. **Adversa:** subregla + términos como `no procede`, `excepción`, `distinguió`, `rectificó`, `modificó`, `superó`, `apartó`, según el contexto.
7. **Citación:** identificador de la sentencia hito dentro del corpus reciente.

No exigir un número fijo de consultas si la evidencia converge antes; ampliar cuando la cobertura sea débil o existan tensiones.

## Papel concreto de las herramientas externas

### `lackeyjb/playwright-skill`

Usar para aumentar capacidad de exploración y automatización de los portales oficiales en entornos de programación: descubrir selectores, formularios, descargas, paginación y rutas resistentes. Aprovechar su enfoque code-first cuando la interacción de navegador sea compleja o deba repetirse. El resultado útil es la automatización del portal oficial, no una conclusión jurídica.

### `microsoft/playwright-mcp`

Usar como opción de navegador MCP cuando el cliente o la arquitectura lo permita. Es especialmente útil para interacción iterativa mediante snapshots estructurados. En producción, preferir su uso detrás del conector jurídico o con restricciones de hosts, autenticación y aislamiento apropiados.

### `jordan-gibbs/hyperresearch`

Usar para aumentar amplitud y profundidad: descomposición, búsqueda en abanico, contradicciones, gap-fill, procedencia, persistencia y cite-check. Configurar la investigación jurídica para que la etapa de autoridad se cierre exclusivamente con fuentes oficiales. No importar sus métricas generales como criterios de fuerza jurídica.

### `vercel-labs/skills`

Usar como multiplicador de capacidades del entorno de desarrollo: descubrir, instalar y actualizar skills compatibles —por ejemplo Playwright— en Claude Code/Codex u otros agentes. No es un buscador, pero facilita incorporar rápidamente herramientas que sí amplían la navegación y la investigación.

### Firecrawl MCP u otros crawlers

Usar solo como canal auxiliar de descubrimiento o extracción cuando aporte cobertura. Restringir consultas jurídicas a formulaciones abstractas y, cuando sea posible, dominios oficiales. Todo hallazgo utilizado debe verificarse de nuevo en la fuente oficial.

## Orquestación recomendada del MCP

`buscar_providencia` no debe hacer una sola consulta. Debe orquestar una estrategia escalonada y devolver cobertura:

1. consultar corpus oficial;
2. ejecutar buscador oficial con varias formulaciones;
3. activar Playwright si el portal requiere interacción;
4. complementar con búsqueda web restringida al dominio oficial;
5. expandir por citas, decisiones relacionadas y búsqueda adversa;
6. deduplicar por identificador/radicado/hash;
7. devolver candidatos con `verificado: false`, procedencia y canales por los que fueron encontrados;
8. pasar los candidatos seleccionados a `verificar_cita` y `leer_providencia`.

`actualizar_linea` debe aplicar la misma arquitectura pero orientada a decisiones posteriores que citen, distingan, precisen, rectifiquen o superen la sentencia hito.

## Señales de cobertura insuficiente

Marcar la búsqueda como incompleta cuando ocurra cualquiera de estas condiciones:

- solo se usó un canal pese a fallar o devolver cero resultados;
- no se consultó el portal oficial de la corporación;
- el portal estaba inaccesible y no se intentó una ruta oficial alternativa;
- los únicos hallazgos provienen de fuentes secundarias;
- no se buscó actualización cuando la regla es decisiva;
- no se ejecutó búsqueda adversa en una cuestión controvertida;
- no se leyó el contexto de la providencia seleccionada.

## Privacidad

Nunca enviar a buscadores externos el expediente, el borrador ni hechos identificables que no sean necesarios. Convertir el problema en una subregla jurídica abstracta. Los metadatos de providencias públicas sí pueden utilizarse para localización y verificación conforme al contrato del conector.
