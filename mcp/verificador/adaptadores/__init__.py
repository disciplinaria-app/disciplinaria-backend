from ..http import ClienteHTTP
from ..modelos import Corporacion
from ..navegador import Navegador
from ..portales import PORTALES
from .base import Adaptador
from .consejo_estado import ConsejoEstado
from .corte_constitucional import CorteConstitucional
from .webrelatoria import CNDJ, CorteSuprema


def construir_adaptadores(http: ClienteHTTP, nav: Navegador) -> dict[Corporacion, Adaptador]:
    return {
        Corporacion.CORTE_CONSTITUCIONAL: CorteConstitucional(http, nav, PORTALES[Corporacion.CORTE_CONSTITUCIONAL]),
        Corporacion.CORTE_SUPREMA: CorteSuprema(http, nav, PORTALES[Corporacion.CORTE_SUPREMA]),
        Corporacion.CONSEJO_ESTADO: ConsejoEstado(http, nav, PORTALES[Corporacion.CONSEJO_ESTADO]),
        Corporacion.CNDJ: CNDJ(http, nav, PORTALES[Corporacion.CNDJ]),
    }


__all__ = ["Adaptador", "construir_adaptadores", "CorteConstitucional", "CorteSuprema", "ConsejoEstado", "CNDJ"]
