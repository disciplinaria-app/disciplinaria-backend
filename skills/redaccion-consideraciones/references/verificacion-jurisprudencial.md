# Protocolo de verificación jurisprudencial

El objetivo es que ninguna cita falsa, errada, descontextualizada o no verificada llegue a la providencia. La fabricación de jurisprudencia es el riesgo más grave; el segundo es la cita auténtica mal usada: identificada correctamente, pero atribuida a la mayoría cuando pertenece a un voto separado, o invocada por una regla que su texto no sostiene.

## 1. Procedimiento por cada cita

1. **Buscar** la providencia por su identificador o por la tesis, con el nombre de la corporación en la consulta. Si se conoce el número, buscar directamente; si solo se conoce la tesis, buscar la subregla y luego identificar la sentencia hito. Formular la consulta como subregla abstracta, sin nombres de partes ni radicado del caso.

2. **Abrir la fuente oficial** (página de relatoría o PDF de la corporación). Leer encabezado, hechos relevantes, problema jurídico, razones decisivas, decisión y, si existen, votos separados. No se fabrica una URL a partir de un patrón de año y número.

3. **Confirmar los cinco datos** contra esa lectura, no contra el resumen del buscador:
   - Corporación (Corte Constitucional / Corte Suprema de Justicia / Consejo de Estado / CNDJ / Sala Jurisdiccional Disciplinaria del CSJ para la línea anterior a 2021).
   - Sala o Sección.
   - Magistrado ponente.
   - Número de sentencia o radicado completo, sin completar ceros ni sufijos por inferencia.
   - Fecha de la decisión (distinta de la fecha de publicación o de carga).

4. **Confirmar la atribución del pasaje**: que la proposición invocada pertenezca a las razones de la mayoría, no a la reseña de un argumento de parte, de una decisión de instancia, de un precedente citado o de un salvamento o aclaración de voto. Una frase dentro de la parte motiva puede ser una tesis que la corporación rechaza.

5. **Confirmar la regla y su pertinencia**: reconstruir supuesto, consecuencia, condiciones y excepciones; verificar que los hechos del precedente y los del caso compartan el supuesto jurídicamente relevante; si difieren, aplicar *distinguishing* expreso.

6. **Confirmar actualidad**: ejecutar la capa de actualización (§2) y la búsqueda adversa.

7. **Resultado**:
   - **Completa** → insertar la cita y referenciarla a pie de página.
   - **Parcial** (falta un dato o la atribución no está clara) → `[VERIFICAR: falta confirmar (dato) de (sentencia)]` y aviso al usuario.
   - **Nula** (no se halla, hay contradicción entre fuentes o el texto no sostiene la regla) → no insertar; reportar que la tesis necesita una sentencia de respaldo confirmada. No sustituirla por otra de memoria.

## 2. Capa de actualización: cuatro años anteriores a la fecha de corte

Toda subregla que sostenga una tesis se investiga en dos capas. La primera es la línea consolidada (sentencia fundadora e hitos de desarrollo), que se conserva siempre. La segunda es la actualización: pronunciamientos de los **cuatro años anteriores a la fecha de corte**, calculada en cada ejecución (fecha de corte = fecha del encargo, salvo que el usuario fije otra, por ejemplo porque el proyecto se fecha en el pasado). La ventana orienta la búsqueda; no excluye un desarrollo decisivo anterior ni una decisión posterior que el usuario aporte.

**Cómo buscar la capa de actualización:**
- Incluir los años de la ventana en la consulta: "[subregla] Corte Constitucional [año]", "[tema] sentencia de unificación [año]", "[falta disciplinaria] CNDJ [año]".
- Ejecutar al menos una búsqueda por subregla con los años de la ventana y, si no hay resultados pertinentes, variar concepto, denominación o portal antes de concluir.
- No limitarse a decisiones que citen nominalmente a la sentencia hito: un desarrollo relevante puede no mencionarla.
- Ejecutar siempre una **búsqueda adversa**: la misma subregla con `excepción`, `no procede`, `distinguió`, `rectificó`, `modificó`, `apartó`, según el contexto.
- Priorizar: sentencias de unificación y de Sala Plena de la Corte Constitucional, sentencias de unificación del Consejo de Estado, providencias de las Salas de Casación de la CSJ y decisiones de la CNDJ, en el orden de fuerza que corresponda a la materia.

**Cómo clasificar el hallazgo reciente (triaje obligatorio):**
- **Confirma**: reitera la subregla sin variación → se cita en cadena con la fundadora como reiteración reciente de la línea.
- **Precisa**: añade matices, criterios de aplicación o subfacetas → se citan ambas; la fundadora aporta la ratio original y la reciente el estado actual del concepto, y el texto muestra esa evolución.
- **Modifica**: la corporación declaró expresamente un cambio de precedente, o la decisión reciente decide el mismo supuesto en sentido incompatible → se advierte al usuario antes de redactar; la línea vigente se cita como fundamento y la anterior solo como contexto.
- **Tensión no resuelta**: decisiones de la misma corporación o de corporaciones distintas resuelven el supuesto de manera divergente sin que una haya rectificado a la otra → se expone la tensión, se justifica la posición adoptada y se advierte al usuario; no se presenta como línea pacífica.

**Reglas de la capa de actualización:**
- La actualización complementa, jamás desplaza: la jurisprudencia fundadora no se elimina por antigua; sí se corrige o excluye la errada, superada o impertinente, con registro en el informe.
- Un cambio de línea no se afirma por una frase aislada; tampoco se descarta por la ausencia de una fórmula de cambio. Ante duda, estudiar decisión, hechos y temporalidad, y mantener la incertidumbre donde corresponda.
- Si no se halla pronunciamiento reciente, se informa: "no se localizaron decisiones adicionales en las fuentes y consultas realizadas hasta [fecha]". No se escribe "la línea no ha cambiado" por ausencia de resultados.
- La sentencia reciente se somete al mismo procedimiento de verificación (§1) que cualquier otra cita.

## 3. Fuentes admisibles y jerarquía

Leer `fuentes-oficiales.md` para portales, fallbacks y registro. En orden:
1. Relatoría oficial o texto oficial de la providencia en el portal de la corporación.
2. Verificador MCP del despacho, si está realmente conectado, con revisión campo por campo.
3. Documento oficial aportado por el usuario, declarado como tal en el informe; su autenticidad no se presume por el membrete.
4. Fuentes secundarias (repositorios institucionales, boletines, blogs): **solo como pista** para localizar. Dos secundarias concordantes no acreditan independencia ni verificación oficial; la cita sostenida únicamente en ellas se marca `[VERIFICAR: confirmar en fuente oficial …]`.

Si dos fuentes discrepan en ponente, fecha o radicado, prevalece la oficial; si la discrepancia es entre dos oficiales, la cita queda como no verificada hasta resolverla. Cuando una sentencia transcribe otra, se diferencia fuente consultada y fuente citada: para afirmar que se verificó la segunda, hay que abrirla.

## 4. Regla sobre salvamentos y aclaraciones de voto

Los salvamentos y aclaraciones de voto carecen de fuerza vinculante y de valor precedencial. No se citan como autoridad. Solo se mencionan si el usuario los invoca expresamente como punto de contraste, y en ese caso se identifican con su autor y naturaleza, nunca como ratio.

## 5. Formato de la nota al pie

Corporación, Sala o Sección, sentencia o radicado, M.P. [nombre], fecha; cuando la cita es textual o la regla es decisiva, añadir el localizador (párrafo, fundamento jurídico o página). Cuando el documento ya tenga un estilo de citación propio, replicarlo en lugar de imponer otro. Las citas textuales se transcriben literalmente; no se entrecomilla una síntesis propia.
