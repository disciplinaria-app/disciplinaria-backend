"""
Orquestación del triage de correspondencia.

Encadena las cuatro etapas del proceso: normalización del correo, extracción
del texto de los adjuntos, cotejo determinista y lectura del agente. Reparte
deliberadamente el trabajo entre lo verificable y lo interpretativo: el cómputo
de términos, la comparación de entidades y la de radicados se resuelven en
código; la identificación de quién suscribe y de qué trata el documento se
confía al agente, y después se somete al cotejo.

Si el agente falla, el proceso no se interrumpe: la ficha se entrega con las
alertas deterministas y la advertencia correspondiente, porque un adjunto
ilegible o un anexo ausente deben avisarse incluso sin lectura del modelo.
"""

import base64
from datetime import date, datetime

from agents import agente_triage
from config import MODEL_TRIAGE
from models.schemas import (
    Alerta,
    AdjuntoEntrada,
    ContextoEnvio,
    DocumentoProcesado,
    ResultadoCotejo,
    Termino,
    TriageResponse,
)
from services import correo as servicio_correo
from services import cotejo as servicio_cotejo
from services import extraccion_pdf

_SEVERIDADES = ("BAJA", "MEDIA", "ALTA")
_CODIGOS_VALIDOS = set(servicio_cotejo.CODIGOS_ALERTA)

# Umbrales en días para graduar la severidad de un término por vencer.
_DIAS_SEVERIDAD_ALTA = 3
_DIAS_SEVERIDAD_MEDIA = 10


def _mayor_severidad(una: str, otra: str) -> str:
    return max(una, otra, key=lambda s: _SEVERIDADES.index(s) if s in _SEVERIDADES else 0)


def _normalizar_severidad(valor) -> str:
    texto = str(valor or "").strip().upper()
    return texto if texto in _SEVERIDADES else "MEDIA"


def _parsear_fecha(valor) -> date | None:
    """Acepta únicamente AAAA-MM-DD; cualquier otro formato se descarta."""
    if not valor or not isinstance(valor, str):
        return None
    try:
        return datetime.strptime(valor.strip()[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _lista_de_textos(valor, limite: int = 20) -> list[str]:
    if not isinstance(valor, list):
        return []
    salida: list[str] = []
    for elemento in valor:
        texto = str(elemento).strip()
        if texto and texto not in salida:
            salida.append(texto)
        if len(salida) >= limite:
            break
    return salida


def _resumen_precotejo(
    entidad_interpelada: str | None,
    radicado_enviado: str | None,
    radicados_hallados: list[str],
) -> str:
    """Informe que se entrega al agente antes de su lectura, para que lo confronte."""
    lineas = [
        f"Entidad a la que el despacho dirigió la comunicación: {entidad_interpelada or '(no informada)'}",
        "  (la comparación con quien suscribe el adjunto queda a tu determinación)",
        f"Radicado remitido por el despacho: {radicado_enviado or '(no informado)'}",
    ]
    if radicados_hallados:
        lineas.append(
            "Radicados detectados en el material recibido: " + ", ".join(radicados_hallados[:10])
        )
        if radicado_enviado:
            coincide = any(
                servicio_cotejo.radicados_equivalentes(radicado_enviado, h)
                for h in radicados_hallados
            )
            lineas.append(
                "Correspondencia de radicados: "
                + ("el remitido aparece citado" if coincide else "el remitido NO aparece citado")
            )
    else:
        lineas.append("No se detectaron radicados en el material recibido.")
    return "\n".join(lineas)


def _construir_termino(datos, advertencias: list[str]) -> Termino | None:
    """
    Construye el término calculando los días en código, no en el modelo.

    Si el agente devuelve una fecha en formato inválido, el término se descarta
    y se advierte: una fecha límite equivocada es peor que ninguna.
    """
    if not isinstance(datos, dict):
        return None
    fecha_limite = _parsear_fecha(datos.get("fecha_limite"))
    fundamento = datos.get("fundamento")
    fundamento = str(fundamento).strip() if fundamento else None

    if datos.get("fecha_limite") and not fecha_limite:
        advertencias.append(
            "El agente señaló una fecha límite en formato no interpretable; se omitió "
            "del término. Verifique el plazo directamente en el documento."
        )

    if not fecha_limite and not fundamento:
        return None

    dias = (fecha_limite - date.today()).days if fecha_limite else None
    return Termino(
        fecha_limite=fecha_limite.isoformat() if fecha_limite else None,
        dias_restantes=dias,
        fundamento=fundamento,
    )


def _alertas_de_termino(termino: Termino | None) -> list[Alerta]:
    """Gradúa la alerta de término a partir de los días efectivamente calculados."""
    if not termino or termino.dias_restantes is None:
        return []
    dias = termino.dias_restantes
    if dias < 0:
        descripcion = (
            f"El término venció el {termino.fecha_limite} (hace {abs(dias)} días). "
            "Verifique si la oportunidad de actuar se encuentra precluida."
        )
        severidad = "ALTA"
    elif dias <= _DIAS_SEVERIDAD_ALTA:
        descripcion = f"El término vence el {termino.fecha_limite}: restan {dias} días."
        severidad = "ALTA"
    elif dias <= _DIAS_SEVERIDAD_MEDIA:
        descripcion = f"El término vence el {termino.fecha_limite}: restan {dias} días."
        severidad = "MEDIA"
    else:
        descripcion = f"El término vence el {termino.fecha_limite}: restan {dias} días."
        severidad = "BAJA"
    return [
        Alerta(
            codigo="TERMINO_CORRIENDO",
            descripcion=descripcion,
            severidad=severidad,
            origen="COTEJO",
        )
    ]


def _alertas_del_modelo(valor, advertencias: list[str]) -> list[Alerta]:
    """Admite solo los códigos del catálogo; descarta y advierte los demás."""
    alertas: list[Alerta] = []
    if not isinstance(valor, list):
        return alertas
    descartados: list[str] = []
    for elemento in valor:
        if not isinstance(elemento, dict):
            continue
        codigo = str(elemento.get("codigo", "")).strip().upper()
        descripcion = str(elemento.get("descripcion", "")).strip()
        if not descripcion:
            continue
        if codigo not in _CODIGOS_VALIDOS:
            if codigo:
                descartados.append(codigo)
            continue
        alertas.append(
            Alerta(
                codigo=codigo,
                descripcion=descripcion,
                severidad=_normalizar_severidad(elemento.get("severidad")),
                origen="MODELO",
            )
        )
    if descartados:
        advertencias.append(
            "El agente propuso alertas con códigos ajenos al catálogo, que se descartaron: "
            + ", ".join(sorted(set(descartados)))
        )
    return alertas


def _fusionar_alertas(deterministas: list[Alerta], del_modelo: list[Alerta]) -> list[Alerta]:
    """
    Unifica las alertas por código.

    Cuando el cotejo y el agente concurren en un mismo hallazgo, la alerta se
    marca como de origen AMBOS y conserva la severidad mayor: la coincidencia
    de dos fuentes independientes refuerza la confiabilidad del aviso.
    """
    fusionadas: dict[str, Alerta] = {}
    for alerta in [*deterministas, *del_modelo]:
        existente = fusionadas.get(alerta.codigo)
        if existente is None:
            fusionadas[alerta.codigo] = alerta.model_copy()
            continue
        existente.severidad = _mayor_severidad(existente.severidad, alerta.severidad)
        if existente.origen != alerta.origen:
            existente.origen = "AMBOS"
        # La descripción determinista cita los datos cotejados; se conserva y se
        # complementa con la lectura del agente.
        if alerta.descripcion not in existente.descripcion:
            existente.descripcion = f"{existente.descripcion} {alerta.descripcion}".strip()
    orden = {"ALTA": 0, "MEDIA": 1, "BAJA": 2}
    return sorted(fusionadas.values(), key=lambda a: orden.get(a.severidad, 3))


def _urgencia_final(propuesta, alertas: list[Alerta]) -> str:
    """
    La urgencia nunca se rebaja por debajo de la alerta más grave.

    El agente puede proponerla, pero una alerta de severidad ALTA impone al
    menos esa urgencia: el sistema debe errar por exceso de aviso.
    """
    urgencia = _normalizar_severidad(propuesta) if propuesta else "BAJA"
    for alerta in alertas:
        urgencia = _mayor_severidad(urgencia, alerta.severidad)
    return urgencia


def _documentos_desde_ingesta(
    adjuntos: list[AdjuntoEntrada], permitir_ocr: bool
) -> list[DocumentoProcesado]:
    """
    Procesa los adjuntos remitidos por la capa de ingesta.

    Los que llegan en base64 se extraen aquí, con el mismo reconocimiento
    óptico que la vía multiparte; los que llegan ya convertidos a texto se
    envuelven sin reprocesarlos.
    """
    documentos: list[DocumentoProcesado] = []
    for adjunto in adjuntos:
        if adjunto.contenido_base64:
            try:
                # El base64 de MIME viene plegado en líneas; se compacta antes de
                # decodificar, sin renunciar a la validación del alfabeto.
                compactado = "".join(adjunto.contenido_base64.split())
                contenido = base64.b64decode(compactado, validate=True)
            except Exception as exc:
                documentos.append(
                    DocumentoProcesado(
                        nombre=adjunto.nombre,
                        advertencias=[f"El adjunto no venía en base64 válido: {exc}"],
                    )
                )
                continue
            documentos.append(
                extraccion_pdf.extraer(contenido, adjunto.nombre, permitir_ocr=permitir_ocr)
            )
            continue

        texto = (adjunto.texto or "").strip()
        documentos.append(
            DocumentoProcesado(
                nombre=adjunto.nombre,
                paginas=0,
                paginas_procesadas=1 if texto else 0,
                metodo="TEXTO_NATIVO" if texto else "NINGUNO",
                caracteres=len(texto),
                texto=texto,
                advertencias=(
                    []
                    if texto
                    else ["El adjunto se recibió sin texto desde la capa de ingesta."]
                ),
            )
        )
    return documentos


async def procesar(
    remitente: str,
    asunto: str = "",
    cuerpo: str = "",
    fecha_recepcion: str | None = None,
    contexto: ContextoEnvio | None = None,
    archivos: list[tuple[str, bytes]] | None = None,
    adjuntos: list[AdjuntoEntrada] | None = None,
    permitir_ocr: bool = True,
) -> TriageResponse:
    """Ejecuta el triage completo y devuelve la ficha de la comunicación."""
    advertencias: list[str] = []
    contexto = contexto or ContextoEnvio()

    # Etapa 1 — aislar el mensaje nuevo de la cadena de respuestas.
    mensaje_actual, cadena_anterior = servicio_correo.limpiar_cuerpo(cuerpo)
    entidad_interpelada = contexto.entidad_interpelada
    if not entidad_interpelada:
        entidad_interpelada = servicio_correo.inferir_entidad_interpelada(cadena_anterior)
        if entidad_interpelada:
            advertencias.append(
                f"La entidad interpelada no se declaró; se dedujo «{entidad_interpelada}» de "
                "la cadena anterior del correo. Confírmela antes de apoyarse en el cotejo."
            )

    # Etapa 2 — extraer el texto de los adjuntos.
    documentos: list[DocumentoProcesado] = [
        extraccion_pdf.extraer(contenido, nombre, permitir_ocr=permitir_ocr)
        for nombre, contenido in (archivos or [])
    ]
    documentos.extend(_documentos_desde_ingesta(adjuntos or [], permitir_ocr))

    ilegibles = [d.nombre for d in documentos if d.metodo == "NINGUNO"]
    legibles = [(d.nombre, d.texto) for d in documentos if d.texto]

    # Etapa 3 — cotejo determinista de radicados sobre todo el material.
    material = "\n\n".join([mensaje_actual, *(t for _, t in legibles)])
    radicados_hallados = servicio_cotejo.extraer_radicados(material)
    precotejo = _resumen_precotejo(
        entidad_interpelada, contexto.radicado_enviado, radicados_hallados
    )

    # Etapa 4 — lectura del agente.
    datos: dict = {}
    fallo_agente: str | None = None
    try:
        datos, advertencias_agente = await agente_triage.ejecutar(
            remitente=remitente,
            asunto=asunto,
            cuerpo=mensaje_actual,
            cadena_anterior=cadena_anterior,
            fecha_recepcion=fecha_recepcion,
            entidad_interpelada=entidad_interpelada,
            radicado_enviado=contexto.radicado_enviado,
            asunto_enviado=contexto.asunto_enviado,
            resumen_cotejo=precotejo,
            documentos=legibles,
            modelo=MODEL_TRIAGE,
        )
        advertencias.extend(advertencias_agente)
    except Exception as exc:
        fallo_agente = str(exc)
        advertencias.append(
            f"El agente de triage no pudo procesar la comunicación ({fallo_agente}). "
            "La ficha contiene únicamente las verificaciones automáticas; el contenido "
            "del documento no fue clasificado."
        )

    if not isinstance(datos, dict):
        # El agente devolvió un JSON válido pero que no es un objeto (una lista,
        # por ejemplo). Se descarta su lectura y se conserva el cotejo.
        advertencias.append(
            "El agente devolvió una estructura JSON inesperada; su lectura se descartó. "
            "La ficha contiene únicamente las verificaciones automáticas."
        )
        fallo_agente = fallo_agente or "estructura JSON inesperada"
        datos = {}

    entidad_remitente = datos.get("entidad_remitente")
    entidad_remitente = str(entidad_remitente).strip() if entidad_remitente else None

    # Cotejo final, ahora sí con la entidad que suscribe el documento.
    resultado_cotejo: ResultadoCotejo = servicio_cotejo.cotejar(
        entidad_esperada=entidad_interpelada,
        entidad_recibida=entidad_remitente,
        radicado_enviado=contexto.radicado_enviado,
        radicados_hallados=radicados_hallados,
    )

    termino = _construir_termino(datos.get("termino"), advertencias)

    alertas_cotejo = servicio_cotejo.alertas_deterministas(
        resultado=resultado_cotejo,
        entidad_esperada=entidad_interpelada,
        entidad_recibida=entidad_remitente,
        cuerpo=mensaje_actual,
        numero_adjuntos=len(documentos),
        documentos_ilegibles=ilegibles,
    )
    alertas_cotejo.extend(_alertas_de_termino(termino))
    alertas = _fusionar_alertas(alertas_cotejo, _alertas_del_modelo(datos.get("alertas"), advertencias))

    tipo_acto = str(datos.get("tipo_acto", "")).strip().upper()
    if tipo_acto not in agente_triage.TIPOS_ACTO:
        if tipo_acto:
            advertencias.append(
                f"El agente clasificó el acto como «{tipo_acto}», ajeno al catálogo; "
                "se registró como OTRO."
            )
        tipo_acto = "OTRO"

    materia = str(datos.get("materia", "")).strip()
    resumen = str(datos.get("resumen", "")).strip()
    if fallo_agente:
        materia = materia or "No determinada: el agente de triage no pudo leer el documento."
        resumen = resumen or (
            "No fue posible clasificar el contenido. Revise las alertas automáticas y lea "
            "el documento directamente."
        )
    else:
        materia = materia or "No determinada."
        resumen = resumen or "El agente no produjo síntesis del documento."

    actuacion = datos.get("actuacion_sugerida")
    actuacion = str(actuacion).strip() if actuacion else None

    return TriageResponse(
        entidad_remitente=entidad_remitente,
        tipo_acto=tipo_acto,
        materia=materia,
        resumen=resumen,
        radicados=_lista_de_textos(datos.get("radicados")) or radicados_hallados[:10],
        expedientes=_lista_de_textos(datos.get("expedientes")),
        requiere_actuacion=bool(datos.get("requiere_actuacion", False)),
        actuacion_sugerida=actuacion,
        termino=termino,
        alertas=alertas,
        urgencia=_urgencia_final(datos.get("urgencia"), alertas),
        documentos=documentos,
        cotejo=resultado_cotejo,
        advertencias=advertencias,
    )
