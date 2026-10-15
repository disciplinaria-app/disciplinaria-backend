"""Puntos de entrada de los portales oficiales.

Las rutas internas de los portales cambian. Todas pueden sobreescribirse con
variables de entorno sin tocar el código, y la herramienta
`diagnosticar_portales` informa cuáles responden hoy. Lo que aquí figura es
el punto de partida documentado en la especificación; su validación en vivo
se registra en docs/portales.md.
"""
from __future__ import annotations

import os

from .modelos import Corporacion


def _env(clave: str, defecto: str) -> str:
    return os.getenv(clave, defecto)


PORTALES: dict[Corporacion, dict[str, str]] = {
    Corporacion.CORTE_CONSTITUCIONAL: {
        "nombre": "Corte Constitucional",
        "base": _env("CC_BASE", "https://www.corteconstitucional.gov.co"),
        "relatoria": _env("CC_RELATORIA", "https://www.corteconstitucional.gov.co/relatoria/"),
        # Patrones de URL de sentencias en la relatoría. Se prueban en orden y se
        # acepta el primero cuyo texto muestre el identificador (el portal devuelve
        # una página «404 Página No Encontrada» con código 200 cuando la ruta no existe).
        "patrones_sentencia": _env("CC_PATRONES",
            "https://www.corteconstitucional.gov.co/relatoria/{anio}/{tipo}-{num3}-{aa}.htm,"
            "https://www.corteconstitucional.gov.co/relatoria/{anio}/{tipo}{num3}-{aa}.htm,"
            "https://www.corteconstitucional.gov.co/relatoria/{anio}/{tipo}-{num}-{aa}.htm,"
            "https://www.corteconstitucional.gov.co/relatoria/{anio}/{tipo}{num}-{aa}.htm"),
        "buscador": _env("CC_BUSCADOR", "https://www.corteconstitucional.gov.co/relatoria/buscador-jurisprudencia"),
    },
    Corporacion.CORTE_SUPREMA: {
        "nombre": "Corte Suprema de Justicia",
        "base": _env("CSJ_BASE", "https://www.cortesuprema.gov.co"),
        "relatoria": _env("CSJ_RELATORIA", "https://consultajurisprudencial.ramajudicial.gov.co/WebRelatoria/csj/index.xhtml"),
        "buscador": _env("CSJ_BUSCADOR", "https://consultajurisprudencial.ramajudicial.gov.co/WebRelatoria/csj/index.xhtml"),
    },
    Corporacion.CONSEJO_ESTADO: {
        "nombre": "Consejo de Estado",
        "base": _env("CE_BASE", "https://www.consejodeestado.gov.co"),
        "relatoria": _env("CE_RELATORIA", "https://samai.consejodeestado.gov.co/TitulacionRelatoria/BuscadorProvidenciasTituladas.aspx"),
        "buscador": _env("CE_BUSCADOR", "https://samai.consejodeestado.gov.co/TitulacionRelatoria/BuscadorProvidenciasTituladas.aspx"),
    },
    Corporacion.CNDJ: {
        "nombre": "Comisión Nacional de Disciplina Judicial",
        "base": _env("CNDJ_BASE", "https://jurisprudencia.ramajudicial.gov.co"),
        "relatoria": _env("CNDJ_RELATORIA", "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml"),
        "buscador": _env("CNDJ_BUSCADOR", "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml"),
    },
}

# Selectores del formulario JSF de las relatorías de la Rama Judicial
# (CSJ y CNDJ comparten la misma aplicación WebRelatoria). Son el punto de
# partida; si el portal cambia, se ajustan por variable de entorno.
SELECTORES_WEBRELATORIA = {
    # Panel plegable que oculta los campos hasta que se expande.
    "panel_criterios": _env("WR_PANEL", "Criterios de búsqueda"),
    # El campo «Tema» es el único con id estable (searchForm:temaInput); los demás
    # llevan ids generados por JSF que cambian entre despliegues del portal.
    "campo_texto": _env("WR_CAMPO_TEXTO", "input[id$=':temaInput']"),
    "boton_buscar": _env("WR_BOTON_BUSCAR", "button[id^='searchForm']:has-text('Buscar'):visible, button:has-text('Buscar'):visible"),
    "filas_resultado": _env("WR_FILAS", "tbody[id$='jurisTable_data'] tr, table[id$='jurisTable'] tbody tr, .ui-datatable-data tr"),
    "enlace_documento": _env("WR_ENLACE", "a[href*='.pdf'], a[href*='Documento'], a[id*='descarg'], a"),
    "siguiente_pagina": _env("WR_SIGUIENTE", ".ui-paginator-next:not(.ui-state-disabled)"),
}

SELECTORES_CC = {
    "selector_modo": _env("CC_SELECTOR_MODO", "#selectBuscador"),
    "modo_texto": _env("CC_MODO_TEXTO", "Texto completo de las providencias"),
    "modo_numero": _env("CC_MODO_NUMERO", "Número de sentencia o auto"),
    "campo_texto": _env("CC_CAMPO_TEXTO", "#textoBuscador"),
    "boton_buscar": _env("CC_BOTON_BUSCAR", "button:has-text('Buscar')"),
}
