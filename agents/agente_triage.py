"""
Agente de TRIAGE DE CORRESPONDENCIA.

A diferencia de los cinco agentes de análisis, que califican providencias
propias, este agente clasifica correspondencia ajena. No emite juicio de
calidad: extrae datos verificables y advierte incongruencias.

Dos decisiones de diseño gobiernan su comportamiento:

1. El cómputo de días no se delega al modelo. El agente solo identifica la
   fecha límite que el documento expresa; los días restantes los calcula el
   orquestador. Un término mal contado es un error que el destinatario no
   puede permitirse.

2. La ausencia de un dato se declara, no se completa. El agente debe devolver
   null o lista vacía antes que inferir un radicado, una fecha o una entidad
   que el documento no contiene.
"""

from .base_agent import llamar_openrouter, extraer_json_respuesta

TIPOS_ACTO = (
    "RESPUESTA_DE_FONDO",
    "ACUSE_DE_RECIBO",
    "REQUERIMIENTO",
    "TRASLADO",
    "NOTIFICACION",
    "CITACION",
    "CONSTANCIA",
    "DEVOLUCION_POR_COMPETENCIA",
    "PUBLICIDAD",
    "OTRO",
)

CODIGOS_ADMITIDOS = (
    "ENTIDAD_DISTINTA",
    "DEVOLUCION_POR_COMPETENCIA",
    "RADICADO_NO_COINCIDE",
    "TERMINO_CORRIENDO",
    "REQUIERE_RESPUESTA",
    "DOCUMENTO_INCOMPLETO",
    "SIN_SUSCRIPCION",
    "DATO_RESERVADO",
)

LIMITE_CUERPO = 4000
LIMITE_CADENA = 2000
LIMITE_ADJUNTOS = 20000

SYSTEM = """Eres un asistente de triage de correspondencia institucional para un despacho
judicial colombiano. Tu función es clasificar lo que llega, no evaluarlo: extraes datos
verificables del correo y de sus adjuntos, y adviertes incongruencias entre lo que el
despacho envió y lo que recibió.

Reglas inderogables:
- No inventes radicados, fechas, entidades, cargos, normas ni cifras. Si un dato no consta
  en el material suministrado, usa null o una lista vacía.
- Distingue el asunto del correo de la materia real del documento. El asunto suele arrastrar
  el texto del mensaje original y resulta engañoso; prevalece siempre el contenido del adjunto.
- Identifica la entidad por quien SUSCRIBE el documento adjunto, no por el dominio del
  remitente ni por el asunto. Denominaciones parecidas pueden corresponder a entidades
  distintas e independientes.
- No calcules días ni plazos. Limítate a señalar la fecha límite que el documento expresa.
- Si el texto está incompleto o fue reconocido ópticamente con errores, dilo en lugar de
  reconstruirlo.

Responde ÚNICAMENTE con un bloque JSON válido, sin texto adicional."""

PLANTILLA = """Clasifica la siguiente comunicación recibida en el correo institucional.

=== DATOS DEL CORREO ===
Remitente: {remitente}
Asunto: {asunto}
Fecha de recepción: {fecha_recepcion}

=== LO QUE EL DESPACHO HABÍA ENVIADO ===
Entidad a la que se dirigió la comunicación: {entidad_interpelada}
Radicado remitido: {radicado_enviado}
Asunto remitido: {asunto_enviado}

=== COTEJO AUTOMÁTICO PREVIO (verificación determinista, para que la confirmes o la descartes) ===
{cotejo}

=== MENSAJE ACTUAL ===
{cuerpo}

=== CADENA ANTERIOR (contexto subordinado; no es el mensaje nuevo) ===
{cadena}

=== DOCUMENTOS ADJUNTOS ===
{adjuntos}

Tareas:
1. Determina quién suscribe el documento y si corresponde a la entidad interpelada.
2. Clasifica el acto en uno de estos tipos exactos: {tipos}.
3. Enuncia la materia sustancial del adjunto en una oración precisa.
4. Extrae los radicados y expedientes que el documento cita, tal como aparecen.
5. Establece si exige actuación del despacho y cuál, y si expresa una fecha límite.
6. Levanta las alertas que correspondan, empleando únicamente estos códigos: {codigos}.
   Usa DEVOLUCION_POR_COMPETENCIA cuando la entidad manifieste no ser competente, advierta
   un envío errado o remita por competencia a otra autoridad. Usa ENTIDAD_DISTINTA cuando
   quien suscribe no sea la entidad interpelada.

Responde con este JSON exacto:
```json
{{
  "entidad_remitente": "<denominación de quien suscribe el documento, o null>",
  "tipo_acto": "<uno de los tipos listados>",
  "materia": "<una oración sobre de qué trata realmente el documento>",
  "resumen": "<dos o tres oraciones sobre el contenido y su consecuencia para el despacho>",
  "radicados": ["<radicado citado tal como aparece>", ...],
  "expedientes": ["<expediente citado tal como aparece>", ...],
  "requiere_actuacion": <true o false>,
  "actuacion_sugerida": "<actuación concreta que debe adelantar el despacho, o null>",
  "termino": {{
    "fecha_limite": "<AAAA-MM-DD, o null si el documento no la expresa>",
    "fundamento": "<fragmento o norma en que se apoya el término, o null>"
  }},
  "alertas": [
    {{"codigo": "<código admitido>", "descripcion": "<hallazgo concreto con apoyo en el texto>", "severidad": "ALTA|MEDIA|BAJA"}}
  ],
  "urgencia": "ALTA|MEDIA|BAJA"
}}
```"""


def _recortar(texto: str, limite: int) -> tuple[str, bool]:
    texto = (texto or "").strip()
    if len(texto) <= limite:
        return texto or "(sin contenido)", False
    return texto[:limite], True


def construir_bloque_adjuntos(documentos: list[tuple[str, str]]) -> tuple[str, bool]:
    """
    Compone el bloque de adjuntos repartiendo el presupuesto de caracteres.

    Reparte el límite por igual entre los documentos para que un anexo
    voluminoso no desplace por completo al oficio principal.
    """
    if not documentos:
        return "(el correo no trae adjuntos legibles)", False

    presupuesto = max(LIMITE_ADJUNTOS // len(documentos), 1500)
    partes: list[str] = []
    recortado = False
    for nombre, texto in documentos:
        cuerpo, corte = _recortar(texto, presupuesto)
        recortado = recortado or corte
        sufijo = "\n[… texto truncado …]" if corte else ""
        partes.append(f"--- Documento: {nombre} ---\n{cuerpo}{sufijo}")
    return "\n\n".join(partes), recortado


async def ejecutar(
    remitente: str,
    asunto: str,
    cuerpo: str,
    cadena_anterior: str,
    fecha_recepcion: str | None,
    entidad_interpelada: str | None,
    radicado_enviado: str | None,
    asunto_enviado: str | None,
    resumen_cotejo: str,
    documentos: list[tuple[str, str]],
    modelo: str | None = None,
) -> tuple[dict, list[str]]:
    """
    Invoca al agente y devuelve (datos crudos, advertencias de procesamiento).

    Las advertencias informan al lector de los recortes aplicados al material,
    para que sepa si la ficha se construyó sobre el documento completo.
    """
    advertencias: list[str] = []

    bloque_cuerpo, cuerpo_recortado = _recortar(cuerpo, LIMITE_CUERPO)
    bloque_cadena, _ = _recortar(cadena_anterior, LIMITE_CADENA)
    bloque_adjuntos, adjuntos_recortados = construir_bloque_adjuntos(documentos)

    if cuerpo_recortado:
        advertencias.append("El cuerpo del correo se truncó para el análisis.")
    if adjuntos_recortados:
        advertencias.append(
            "Uno o más adjuntos se truncaron para el análisis; la ficha no cubre su "
            "contenido íntegro."
        )

    prompt = PLANTILLA.format(
        remitente=remitente or "(no informado)",
        asunto=asunto or "(sin asunto)",
        fecha_recepcion=fecha_recepcion or "(no informada)",
        entidad_interpelada=entidad_interpelada or "(no informada)",
        radicado_enviado=radicado_enviado or "(no informado)",
        asunto_enviado=asunto_enviado or "(no informado)",
        cotejo=resumen_cotejo,
        cuerpo=bloque_cuerpo,
        cadena=bloque_cadena or "(no hay cadena anterior)",
        adjuntos=bloque_adjuntos,
        tipos=", ".join(TIPOS_ACTO),
        codigos=", ".join(CODIGOS_ADMITIDOS),
    )

    raw = await llamar_openrouter(
        SYSTEM,
        prompt,
        modelo=modelo,
        max_tokens=3000,
        temperatura=0.0,
    )
    return extraer_json_respuesta(raw), advertencias
