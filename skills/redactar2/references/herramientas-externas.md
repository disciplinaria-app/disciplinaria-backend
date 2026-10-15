# Herramientas externas como ampliación de búsqueda oficial

Fecha de contraste externo: 28 de septiembre de 2026.

## Regla de arquitectura

Las herramientas externas se evalúan por una pregunta concreta: **¿aumentan la capacidad real de localizar, recuperar y contrastar jurisprudencia en los portales oficiales de la Corte Constitucional, Corte Suprema de Justicia, Consejo de Estado y Comisión Nacional de Disciplina Judicial?**

Usarlas como multiplicadores de búsqueda, no como autoridades jurídicas. La autoridad final sigue siendo el texto oficial de la providencia.

Separar cuatro capas que pueden cooperar:

1. **Redactar2** formula subreglas, decide qué buscar, clasifica la fuerza del precedente y redacta.
2. **Redactar2 · Verificador** orquesta la búsqueda de producción, recupera y contrasta evidencia oficial.
3. **Navegadores/agentes de búsqueda** amplían acceso a portales dinámicos y cobertura de consultas.
4. **Herramientas de investigación profunda** amplían formulaciones, siguen citas, detectan contradicciones, rellenan huecos y preservan procedencia.

Leer también `busqueda-jurisprudencial-oficial.md`, que contiene el algoritmo de búsqueda multicanal y la estrategia por corporación.

## 1. lackeyjb/playwright-skill — útil para buscar mejor en portales oficiales

Repositorio: https://github.com/lackeyjb/playwright-skill

La documentación actual lo presenta como automatización Playwright code-first para agentes, capaz de escribir y ejecutar programas ad hoc con bucles, aserciones, múltiples contextos e interceptación de red. Esto lo hace especialmente útil para portales judiciales con formularios, paginación, JavaScript o descargas generadas dinámicamente.

### Integración

- **Claude Code/Codex o agente con ejecución local:** permitir que Redactar2 o el desarrollador use esta skill para explorar directamente relatorías oficiales, construir consultas repetibles y diagnosticar cambios de interfaz.
- **Word/producción:** no depender de que esa skill local exista. Incorporar la automatización resultante dentro de `redactar2-mcp` con Playwright de servidor, o usar un Playwright MCP interno realmente conectado.
- Usar navegador solo contra dominios autorizados y respetar términos, `robots.txt`, límites de tasa y controles técnicos.

Su finalidad dentro del proyecto es **abrir más rutas de búsqueda oficial**, no verificar por sí sola el sentido jurídico de una sentencia.

## 2. Microsoft Playwright MCP — navegador de producción o diagnóstico

Repositorio: https://github.com/microsoft/playwright-mcp

Expone control de navegador mediante MCP y snapshots estructurados. Es una vía útil para consultas iterativas en portales dinámicos.

### Integración preferida

- Primera opción: Playwright directamente dentro de los adaptadores de `redactar2-mcp`.
- Segunda opción: Playwright MCP como servicio interno o con controles estrictos, consumido por el verificador.
- Restringir hosts a los dominios judiciales necesarios cuando la herramienta lo permita.
- No exponer un navegador genérico público como si fuera el verificador jurídico.

## 3. jordan-gibbs/hyperresearch — ampliar amplitud, profundidad y búsqueda adversa

Repositorio: https://github.com/jordan-gibbs/hyperresearch

Su canalización actual incorpora descomposición, búsqueda de amplitud, análisis de contradicciones, investigación en profundidad, críticos adversariales, gap-fill, persistencia y cite-check. Esos mecanismos son directamente útiles para evitar búsquedas jurisprudenciales estrechas.

### Integración

Si Hyperresearch está realmente disponible en Claude Code/Codex:

- formular la consulta de investigación con `domain_notes` jurídicos;
- priorizar/restringir la adquisición decisiva a dominios oficiales;
- usar la búsqueda de amplitud para generar múltiples formulaciones por subregla;
- seguir citas y decisiones relacionadas;
- construir el grafo de tensiones y buscar qué fuente derrotaría la tesis;
- ejecutar gap-fill antes de cerrar una línea;
- usar su procedencia y cite-check para controlar unión afirmación-fuente.

Si no está disponible dentro de Word, **portar esos patrones al orquestador de `redactar2-mcp`**: manifiesto reanudable, expansión por citas, búsqueda adversa, deduplicación, contradicciones y verificación final.

No usar índices, puntuaciones o fuentes secundarias de Hyperresearch para reemplazar jerarquía, ratio o fuente oficial.

## 4. vercel-labs/skills — multiplicador para instalar capacidades

Repositorio: https://github.com/vercel-labs/skills

Es un CLI para descubrir, instalar, actualizar y usar Agent Skills en numerosos agentes. No busca jurisprudencia por sí mismo, pero sí permite **incorporar rápidamente skills que amplían la navegación y la investigación**, incluido Playwright, en los entornos de desarrollo o de agentes compatibles.

Usarlo para mantener actualizadas las capacidades auxiliares de Claude Code/Codex y probarlas contra los cuatro portales. No presentarlo como fuente de información jurídica.

## 5. Firecrawl MCP y buscadores web — descubrimiento auxiliar

Firecrawl puede buscar y extraer páginas; buscadores generales pueden localizar URLs que los buscadores internos no muestran bien. Utilizarlos como **canal de descubrimiento**, preferiblemente restringido con dominios oficiales. Todo candidato utilizado en la providencia debe regresar al portal oficial para verificación.

No enviarles datos del expediente cuando basta una subregla abstracta.

## 6. Destinos oficiales prioritarios

| Corporación | Punto de entrada verificado | Uso de herramientas |
|---|---|---|
| Corte Constitucional | `https://www.corteconstitucional.gov.co/relatoria/` | HTTP/buscador oficial; Playwright si cambia el formulario; búsqueda `site:` oficial como descubrimiento |
| Corte Suprema de Justicia | sistema de consulta y relatorías por Sala | seleccionar Sala, combinar texto/ponente/fecha/fuente formal; Playwright en flujos dinámicos |
| Consejo de Estado | Biblioteca Digital / Jurisprudencia de SAMAI | separar buscador de jurisprudencia de consulta de procesos; Playwright si la interfaz lo exige |
| CNDJ | `https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml` | adaptador específico JSF; Playwright especialmente útil para estado y paginación |

## 7. Política de escalamiento

### Cita conocida

`verificar_cita` → HTTP oficial → Playwright oficial → descubrimiento restringido a dominio → regreso a fuente oficial.

### Precedente por subregla

`buscar_providencia` debe lanzar varias formulaciones y canales, no una consulta única. Combinar relatoría, búsqueda oficial, Playwright, búsqueda `site:`, seguimiento de citas y búsqueda adversa. Todo candidato queda `verificado: false` hasta contraste final.

### Actualización de línea

`actualizar_linea` debe buscar sobre los cuatro años anteriores a la fecha de corte (ventana calculada por el orquestador en cada llamada, no fijada en el código), seguir la cita de la sentencia hito y buscar además decisiones que distingan, limiten, rectifiquen o superen la regla.

### Portal difícil

HTTP → Playwright → ruta oficial alternativa → descubrimiento web. Distinguir `sin_resultados` de `portal_no_disponible`, `bloqueada`, `timeout` y `discrepante`.

## 8. Requisitos de producción para que realmente aumente la capacidad

`redactar2-mcp` debe incorporar o consumir:

- adaptador individual por corporación;
- generador de variantes de consulta;
- estrategia HTTP → Playwright;
- búsqueda web restringida a dominios oficiales como canal auxiliar;
- expansión por citas y precedentes relacionados;
- búsqueda adversa y de cambio de precedente;
- caché/corpus oficial con hash y fecha;
- deduplicación por identificador, radicado, URL y hash;
- procedencia por canal de descubrimiento y URL oficial final;
- integridad de citas literales;
- manifiesto reanudable para trabajos largos;
- estados de fallo técnicamente distintos;
- filtro de prompt injection en contenido web.

El servidor sigue sin redactar: recupera evidencia. Redactar2 interpreta, clasifica y aplica.

## 9. Criterio de éxito

La integración se considera útil solo si, en pruebas reales, encuentra providencias oficiales que una búsqueda simple no localiza o recupera correctamente portales que requieren interacción, **sin aumentar falsos positivos**.

Probar al menos:

1. una providencia conocida por corporación;
2. una consulta temática sin número por corporación;
3. una consulta que requiera navegador;
4. una línea con sentencia fundadora y actualización reciente;
5. una fuente adversa o de distinguishing;
6. metadatos deliberadamente errados;
7. ratio presente solo en salvamento/aclaración;
8. portal caído o timeout sin convertirlo en inexistencia;
9. búsqueda secundaria que encuentre la URL, seguida de verificación oficial;
10. privacidad y prompt injection.

Una skill instalada, por sí sola, no demuestra que estas pruebas funcionen. La capacidad debe estar conectada y probada en el entorno real.
