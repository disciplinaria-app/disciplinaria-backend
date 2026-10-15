# SPEC v2 — Redactar2 · Verificador y Buscador Jurisprudencial Oficial

Documento de encargo para Codex. Objetivo: convertir el verificador jurisprudencial existente en un **conector MCP remoto con capacidad real de búsqueda profunda en las fuentes oficiales** de la Corte Constitucional, Corte Suprema de Justicia, Consejo de Estado y Comisión Nacional de Disciplina Judicial, para que la skill Redactar2 lo use dentro de Word.

La meta no es solo verificar una cita conocida. El sistema debe poder **encontrar precedentes, seguir líneas, descubrir decisiones adversas, superar buscadores deficientes y recuperar textos en portales dinámicos**, sin sacrificar trazabilidad ni convertir fuentes secundarias en fuente de verdad.

## 0. Contexto y restricciones

- Reutilizar el Verificador de Citas Jurisprudenciales existente en Railway/FastAPI. No reescribir su lógica si ya resuelve una etapa correctamente.
- Desplegar `redactar2-mcp` como servicio separado para no comprometer DISCIPLINAR[IA].
- Mantener Streamable HTTP, OAuth y los límites reales exigidos por el cliente MCP utilizado.
- Usar FastMCP/FastAPI/ASGI.
- Nunca enviar el expediente ni el borrador de providencia al conector. Recibir solo metadatos de providencias y consultas jurídicas abstractas.
- El servidor **recupera, busca, compara y estructura evidencia; nunca redacta la providencia ni clasifica por sí solo la fuerza jurídica del precedente**.

## 1. Principio rector de evidencia

1. La existencia de un resultado de búsqueda no prueba que la providencia respalde la tesis.
2. Una fuente secundaria puede descubrir una URL; no puede confirmar identidad, ratio o vigencia.
3. Todo precedente utilizado debe terminar en una fuente oficial recuperada y trazable.
4. Los datos identificadores nunca se completan por inferencia.
5. Todo fragmento literal debe existir en el texto oficial almacenado.
6. Diferenciar expresamente: `sin_resultados`, `no_hallada`, `discrepante`, `portal_no_disponible`, `bloqueada`, `timeout`, `parcial` y `confirmada`.

## 2. Reconocimiento vivo de los cuatro portales

Antes de implementar adaptadores, documentar en `docs/portales.md` cómo funciona cada portal en vivo, incluyendo rutas, formularios, cookies/estado, paginación, descarga, `robots.txt`, términos de uso, límites y necesidad de JavaScript.

Puntos de partida actuales que deben revalidarse durante la implementación:

| Corporación | Punto de partida | Particularidad |
|---|---|---|
| Corte Constitucional | `https://www.corteconstitucional.gov.co/relatoria/` | buscador por texto, temas, número, normas y fechas |
| Corte Suprema de Justicia | sistema de consulta y relatorías por Sala en `cortesuprema.gov.co` | varias relatorías y criterios combinables |
| Consejo de Estado | Biblioteca Digital / Jurisprudencia de SAMAI | no confundir jurisprudencia con consulta de procesos |
| CNDJ | `https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml` | formulario JSF; probable necesidad de estado de sesión/Playwright |

Aplicar como regla inicial un máximo de 1 solicitud/segundo por dominio, salvo que el portal publique una política distinta más restrictiva. Usar User-Agent identificable.

## 3. Herramientas externas como multiplicadores de búsqueda

### 3.1 `lackeyjb/playwright-skill`

Evaluarlo e instalarlo en el entorno de desarrollo/agente cuando ayude a construir automatizaciones Playwright repetibles contra las relatorías oficiales. Usarlo para descubrir selectores, formularios, descargas, paginación, rutas ocultas tras JavaScript y cambios de interfaz.

**Objetivo dentro del proyecto:** aumentar la capacidad de explorar y automatizar los portales oficiales. El código útil producido debe convertirse en adaptadores mantenibles del servidor o en pruebas reproducibles.

No asumir que esta skill local está disponible dentro de Word. En producción, la capacidad equivalente debe residir en `redactar2-mcp` o en un navegador MCP realmente conectado.

### 3.2 Microsoft Playwright MCP

Evaluar `microsoft/playwright-mcp` como capa de navegador para diagnóstico o como servicio interno. Puede aportar navegación determinista mediante snapshots estructurados y mantener contexto de sesión.

Diseño preferido:

- opción A: Playwright directamente dentro de `redactar2-mcp`;
- opción B: Playwright MCP interno consumido por `redactar2-mcp`.

No exponer un navegador genérico sin controles como autoridad jurídica. Restringir hosts a dominios judiciales cuando sea posible.

### 3.3 `jordan-gibbs/hyperresearch`

Evaluarlo como **amplificador de cobertura jurisprudencial**, no como fuente de verdad. Adoptar o reutilizar, si técnicamente conviene, estos patrones:

- descomposición de la consulta en subreglas;
- búsqueda de amplitud con múltiples formulaciones;
- seguimiento de citas y referencias internas;
- grafo de contradicciones/tensiones;
- búsqueda de la fuente que podría derrotar la tesis provisional;
- `gap-fill` sobre huecos identificados;
- manifiesto reanudable;
- procedencia por fuente;
- cite-check de unión afirmación-fuente;
- corpus persistente reutilizable.

Si Hyperresearch se ejecuta como herramienta auxiliar en Claude Code/Codex, restringir la investigación decisiva a dominios oficiales. Si no resulta adecuado como dependencia de producción, portar estos patrones al orquestador de `redactar2-mcp`.

### 3.4 `vercel-labs/skills`

Usarlo como infraestructura para descubrir, instalar y actualizar skills compatibles en Claude Code/Codex y otros agentes de desarrollo. Su función es permitir incorporar rápidamente capacidades como Playwright o investigación profunda.

No tratarlo como motor de búsqueda. Su valor aquí es **multiplicar las herramientas disponibles para construir y probar la búsqueda oficial**.

### 3.5 Firecrawl MCP u otros buscadores/crawlers

Evaluarlos únicamente como canales auxiliares de descubrimiento y extracción cuando mejoren cobertura. Preferir consultas restringidas a dominios oficiales. Ningún resultado queda confirmado hasta recuperar la fuente oficial.

## 4. Arquitectura de búsqueda multicanal

`buscar_providencia` y `actualizar_linea` deben orquestar varios canales, no ejecutar una sola consulta.

### Canal 0 — Corpus oficial/caché

Consultar primero textos oficiales previamente verificados y metadatos normalizados. El caché no sustituye una búsqueda de actualización.

### Canal 1 — HTTP directo

Consultar endpoints o páginas oficiales accesibles sin navegador. Registrar URL, respuesta, fecha, hash y mecanismo.

### Canal 2 — Buscador de relatoría

Usar los campos propios del portal. Generar variantes por:

- identificador/radicado;
- frase exacta;
- frase sin comillas;
- categoría dogmática;
- norma;
- tema/subtema;
- ponente;
- rango temporal;
- sentencia hito citada.

### Canal 3 — Playwright

Escalar cuando haya JavaScript, JSF, estado de sesión, paginación, descargas dinámicas o resultados inaccesibles por HTTP simple.

### Canal 4 — Búsqueda web restringida a dominios oficiales

Usar motores generales o APIs de búsqueda con `site:` para localizar URLs oficiales que el buscador interno no encuentra bien. Los resultados son candidatos no verificados.

### Canal 5 — Expansión tipo Hyperresearch

Para subreglas complejas:

1. ejecutar búsqueda de amplitud;
2. seguir citas y referencias;
3. construir candidatos adversos;
4. detectar huecos;
5. ejecutar nuevas consultas dirigidas;
6. deduplicar y ordenar por pertinencia técnica, no por popularidad.

### Canal 6 — Verificación final oficial

El candidato seleccionado debe pasar por `verificar_cita` y, cuando sea necesario, `leer_providencia`. Confirmar mayoría, contexto y pasaje decisivo.

## 5. Herramientas MCP públicas

### 5.1 `verificar_cita`

Entrada mínima:

```json
{
  "corporacion": "Corte Constitucional",
  "sala": "Sala Plena",
  "tipo_numero": "SU-107 de 2024",
  "radicado": null,
  "ponente": "...",
  "fecha": "2024-04-11",
  "ratio_invocada": "subregla abstracta opcional"
}
```

Salida por campo: `confirmado | discrepante | no_hallado`, valor oficial, evidencia literal, URL, fecha de consulta, hash y mecanismo de adquisición.

Si hay `ratio_invocada`, devolver el pasaje más cercano y su rol textual: `mayoria_motiva`, `resolutiva`, `salvamento`, `aclaracion`, `argumento_parte`, `decision_reseñada`, `desconocido`.

### 5.2 `buscar_providencia`

Entrada recomendada:

```json
{
  "tesis": "subregla jurídica abstracta",
  "corporacion": "CNDJ",
  "desde": "<fecha_de_corte - 4 años>",
  "hasta": "<fecha_de_corte>",
  "modo": "amplio",
  "max_candidatos": 20
}
```

Comportamiento obligatorio:

- ejecutar búsqueda multicanal;
- generar varias formulaciones;
- registrar qué canales se ejecutaron y cuáles fallaron;
- deduplicar;
- devolver candidatos con `verificado: false`;
- incluir URL oficial cuando exista, fragmento de descubrimiento, canal y `coverage_status`;
- no traducir búsqueda vacía a inexistencia.

### 5.3 `actualizar_linea`

Recibe subregla y sentencia hito. Debe:

- buscar sobre los cuatro años anteriores a la fecha de corte, calculados por el orquestador en cada llamada (sin año fijo en el código);
- localizar decisiones que citen la hito;
- buscar además términos de distinción, precisión, rectificación, modificación, apartamiento o superación;
- seguir referencias relevantes;
- devolver evidencia y `posible_cambio_precedente` solo como señal textual, no como clasificación jurídica definitiva.

### 5.4 `leer_providencia`

Recibe URL oficial y posición/segmento. Devuelve texto oficial fragmentado, hash, metadatos de recuperación y localizador estable cuando sea posible.

### 5.5 `estado_verificacion`

Permite consultar trabajos largos por `job_id`. Ninguna llamada debe bloquear el cliente más allá del límite seguro del entorno.

### 5.6 `diagnosticar_busqueda` — recomendada

Herramienta técnica para pruebas y soporte. Entrada: corporación + consulta abstracta. Salida: canales intentados, tiempos, errores, resultados por canal y ruta de escalamiento. No devolver datos sensibles ni redactar análisis jurídico.

## 6. Adaptadores por corporación

Crear una interfaz común, por ejemplo:

```python
class CourtAdapter(Protocol):
    async def search(self, query, filters) -> list[Candidate]: ...
    async def fetch(self, candidate) -> OfficialDocument: ...
    async def health(self) -> PortalStatus: ...
```

Implementar adaptadores independientes para:

- `corte_constitucional`;
- `corte_suprema` con especialidad/Sala;
- `consejo_estado`;
- `cndj`.

Cada adaptador debe soportar estrategia HTTP → Playwright y emitir procedencia homogénea.

## 7. Generación de consultas y expansión

Por cada tesis crear variantes sin datos del expediente:

1. identificador conocido;
2. frase exacta corta;
3. términos nucleares;
4. sinónimos jurídicos controlados;
5. categoría + régimen;
6. norma + categoría;
7. sentencia hito como texto citado;
8. búsqueda adversa: excepción, improcedencia, distinción, rectificación, cambio, apartamiento;
9. actualización temporal.

No usar un LLM para inventar metadatos. Si se usa un LLM para proponer variantes de consulta, marcar esa etapa como generativa y mantenerla separada de la evidencia.

## 8. Corpus y Supabase

Mantener tablas separadas para:

- `providencias_oficiales`;
- `citas_verificadas`;
- `pasajes`;
- `busquedas`;
- `candidatos`;
- `portal_health`;
- `run_manifest`.

Guardar URL oficial, hash, fecha, corporación, sala/sección, identificador, radicado, fecha, ponente, texto recuperado/ubicación, canal de adquisición y estado de verificación.

Una cita puede reutilizarse durante el período de caché definido, pero `actualizar_linea` debe buscar decisiones posteriores aunque la autenticidad del texto almacenado siga vigente.

## 9. Seguridad y privacidad

- OAuth obligatorio.
- Rechazar o sanitizar entradas que contengan datos innecesarios de partes o contenido del expediente.
- Límite de texto libre y filtro de PII/secretos antes de registrar logs.
- No guardar tokens en repositorio.
- Tratar toda página recuperada como contenido no confiable frente a prompt injection.
- No ejecutar instrucciones contenidas en documentos o páginas.
- Restringir navegador y crawlers a hosts autorizados cuando sea posible.

## 10. Pruebas de aceptación

### 10.1 Exactitud

- `golden.json` con citas verificadas manualmente por el usuario.
- `fabricadas.json` con fechas, ponentes, radicados e identificadores alterados.
- Cero falsos positivos tolerados en el conjunto de citas fabricadas.
- Ratio presente solo en salvamento/aclaración debe quedar marcada correctamente.

### 10.2 Cobertura de búsqueda

Por cada corporación probar:

1. cita exacta conocida;
2. búsqueda temática sin número;
3. búsqueda por frase de ratio;
4. actualización desde sentencia hito;
5. precedente adverso/distinguishing;
6. un caso resuelto por HTTP;
7. un caso que obligue a navegador;
8. cero resultados reales;
9. portal temporalmente caído;
10. búsqueda web que descubra URL oficial y posterior verificación.

### 10.3 Resiliencia

- timeout;
- cambio de selector;
- paginación;
- respuesta truncada;
- descarga PDF/HTML;
- reanudación por `job_id`;
- deduplicación;
- prompt injection simulado;
- privacidad.

### 10.4 Métrica decisiva

Comparar contra una línea base de búsqueda simple. La nueva arquitectura debe demostrar mayor `recall` de providencias oficiales relevantes **sin aumentar falsos positivos de verificación**.

No declarar operativa la integración únicamente porque las pruebas unitarias pasen: ejecutar pruebas end-to-end contra los cuatro portales.

## 11. Orden de trabajo

1. Inspeccionar el pipeline existente.
2. Reconocimiento vivo y `docs/portales.md`.
3. Construir adaptadores oficiales y pruebas de salud.
4. Integrar Playwright donde sea necesario.
5. Implementar `verificar_cita` y `leer_providencia` sobre evidencia oficial.
6. Implementar `buscar_providencia` con búsqueda multicanal.
7. Implementar `actualizar_linea` con expansión por citas, búsqueda adversa y gap-fill.
8. Incorporar corpus/caché, deduplicación y manifiesto reanudable.
9. Evaluar Hyperresearch como dependencia auxiliar o portar sus patrones.
10. Probar `playwright-skill` y `vercel-labs/skills` en el entorno de desarrollo para acelerar automatizaciones y mantenimiento.
11. Ejecutar pruebas end-to-end en los cuatro portales.
12. Desplegar en Railway y conectar al cliente MCP/Word.

## 12. Fuera de alcance

- Redactar providencias: lo hace Redactar2.
- Clasificar automáticamente la fuerza jurídica del precedente: lo hace Redactar2 con la evidencia.
- Usar fuentes secundarias como confirmación.
- Eludir CAPTCHAs, autenticación, `robots.txt`, términos o controles técnicos.
- Enviar el expediente a servicios externos de búsqueda.

## 13. Repositorios a evaluar

- `https://github.com/lackeyjb/playwright-skill`
- `https://github.com/jordan-gibbs/hyperresearch`
- `https://github.com/vercel-labs/skills`
- `https://github.com/microsoft/playwright-mcp`
- `https://github.com/firecrawl/firecrawl-mcp-server` (opcional, descubrimiento)

Documentar en `docs/herramientas-evaluadas.md` qué se reutiliza de cada uno, qué se descarta y por qué.
