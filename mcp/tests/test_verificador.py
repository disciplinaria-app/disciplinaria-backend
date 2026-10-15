"""Pruebas del verificador con documentos sintéticos.

Ninguna cita de estas pruebas es real; no deben usarse en providencias.
Las pruebas no acceden a internet: el cliente HTTP se sustituye por uno
que sirve HTML fabricado.
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["PLAYWRIGHT_HABILITADO"] = "0"

from verificador import comparar, consultas, texto  # noqa: E402
from verificador.cache import Corpus  # noqa: E402
from verificador.http import Respuesta  # noqa: E402
from verificador.servicio import Servicio  # noqa: E402

SENTENCIA_SINTETICA = """<html><head><title>T-999/99 Corte Constitucional de Colombia</title></head><body>
<p>Sentencia T-999/99</p>
<p>Referencia: expediente T-0000000</p>
<p>Magistrado Ponente: Dr. Nombre Ficticio Apellidouno Apellidodos</p>
<p>Bogotá D.C., nueve (9) de septiembre de mil novecientos noventa y nueve (1999) — 9 de septiembre de 1999</p>
<p>La Sala Novena de Revisión de la Corte Constitucional</p>
<h2>I. ANTECEDENTES</h2>
<p>El accionante sostuvo que la entidad vulneró su derecho porque la respuesta no fue de fondo y afirmó que la mora era injustificada.</p>
<p>""" + "Relato de hechos. " * 40 + """</p>
<h2>II. CONSIDERACIONES DE LA CORTE</h2>
<p>La subregla aplicable indica que el derecho de petición exige una respuesta de fondo, clara, congruente y oportuna, y que la mora administrativa injustificada vulnera el debido proceso.</p>
<p>""" + "Desarrollo de la consideración. " * 60 + """</p>
<h2>III. DECISIÓN</h2>
<p>RESUELVE: Primero. CONCEDER el amparo.</p>
<h2>SALVAMENTO DE VOTO</h2>
<p>El suscrito magistrado se aparta porque considera que la tutela era improcedente por existir otro medio de defensa judicial idóneo.</p>
</body></html>"""


class ClienteFalso:
    """Sirve HTML fabricado para la URL directa y 404 para lo demás."""

    def __init__(self, html: str, url_ok: str):
        self.html, self.url_ok = html, url_ok
        self.llamadas: list[str] = []

    async def obtener(self, url, params=None, metodo="GET", datos=None):
        self.llamadas.append(url)
        if url == self.url_ok:
            return Respuesta(estado="ok", url_inicial=url, url_final=url, codigo=200,
                             contenido=self.html.encode("utf-8"), tipo="text/html")
        return Respuesta(estado="sin_resultados", url_inicial=url, url_final=url, codigo=404, detalle="HTTP 404")

    async def cerrar(self):
        pass


def servicio_con_html(html: str, url_ok: str) -> tuple[Servicio, ClienteFalso]:
    s = Servicio(corpus=Corpus(tempfile.mkdtemp()))
    falso = ClienteFalso(html, url_ok)
    s.http = falso
    for a in s.adaptadores.values():
        a.http = falso
    return s, falso


class TestComparar(unittest.TestCase):
    def test_canoniza_identificadores_cc(self):
        for v in ("T-999/99", "T-999 de 1999", "Sentencia T 999-99", "t-999/1999"):
            self.assertEqual(comparar.canonizar_identificador(v), "T-999/1999")
        self.assertEqual(comparar.canonizar_identificador("SU-107 de 2024"), "SU-107/2024")

    def test_canoniza_csj_y_radicado(self):
        self.assertEqual(comparar.canonizar_identificador("SP1234-2021"), "SP1234-2021")
        self.assertEqual(comparar.canonizar_identificador("11001-03-15-000-2019-01234-00"), "11001031500020190123400")

    def test_fechas(self):
        self.assertEqual(comparar.parsear_fecha("9 de septiembre de 1999").isoformat(), "1999-09-09")
        self.assertEqual(comparar.parsear_fecha("1999-09-09").isoformat(), "1999-09-09")
        self.assertIsNone(comparar.parsear_fecha("31 de febrero de 1999"))

    def test_ponente(self):
        self.assertTrue(comparar.ponente_coincide("Apellidouno Apellidodos", "Nombre Ficticio Apellidouno Apellidodos"))
        self.assertFalse(comparar.ponente_coincide("Otro Magistrado", "Nombre Ficticio Apellidouno Apellidodos"))


class TestTexto(unittest.TestCase):
    def test_segmenta_y_asigna_roles(self):
        t, meta = texto.html_a_texto(SENTENCIA_SINTETICA)
        bloques = texto.segmentar(t, tamano=800)
        roles = {b.rol for b in bloques}
        self.assertIn("mayoria_motiva", roles)
        self.assertIn("resolutiva", roles)
        self.assertIn("salvamento", roles)
        self.assertIn("argumento_parte", roles)
        self.assertEqual(meta["title"], "T-999/99 Corte Constitucional de Colombia")

    def test_localiza_pasaje(self):
        t, _ = texto.html_a_texto(SENTENCIA_SINTETICA)
        frag, pos, sim = texto.localizar_pasaje(t, "respuesta de fondo, clara, congruente y oportuna")
        self.assertGreater(pos, 0)
        self.assertEqual(sim, 1.0)
        self.assertIn("congruente", frag)


class TestPrivacidad(unittest.TestCase):
    def test_rechaza_datos_del_expediente(self):
        self.assertFalse(consultas.revisar_entrada("accionante Juan Pérez Gómez contra EPS").aceptada)
        self.assertFalse(consultas.revisar_entrada("radicado 11001-03-15-000-2019-01234-00").aceptada)
        self.assertFalse(consultas.revisar_entrada("c.c. 1.234.567.890 mora").aceptada)
        self.assertTrue(consultas.revisar_entrada("mora administrativa plazo razonable debido proceso").aceptada)

    def test_variantes_incluyen_adversa_y_actualizacion(self):
        v = consultas.variantes("ilicitud sustancial deber funcional", "CNDJ", 2022, 2026, "SU-1/2020")
        familias = {x["familia"] for x in v}
        self.assertTrue({"frase_exacta", "adversa", "actualizacion", "citacion_hito", "sinonimo"} <= familias)
        self.assertEqual(len(v), len({x["consulta"].lower() for x in v}))


class TestServicio(unittest.TestCase):
    URL = "https://www.corteconstitucional.gov.co/relatoria/1999/T-999-99.htm"

    def run_async(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    def test_verifica_cita_correcta(self):
        s, _ = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.verificar_cita("Corte Constitucional", tipo_numero="T-999 de 1999",
                                            ponente="Apellidouno Apellidodos", fecha="1999-09-09",
                                            sala="Sala Novena de Revisión",
                                            ratio_invocada="respuesta de fondo clara congruente y oportuna"))
        self.assertEqual(r.estado_global, "confirmada")
        self.assertEqual(r.campos["identificador"].estado, "confirmado")
        self.assertEqual(r.campos["ponente"].estado, "confirmado")
        self.assertEqual(r.campos["fecha"].estado, "confirmado")
        self.assertEqual(r.campos["sala"].estado, "confirmado")
        self.assertEqual(r.pasaje.rol, "mayoria_motiva")
        self.assertFalse(r.solo_en_salvamento)
        self.assertEqual(r.url_oficial, self.URL)
        self.assertTrue(r.procedencia.sha256)

    def test_detecta_ponente_y_fecha_fabricados(self):
        s, _ = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.verificar_cita("CC", tipo_numero="T-999/99", ponente="Magistrado Inventado", fecha="2001-01-01"))
        self.assertEqual(r.estado_global, "discrepante")
        self.assertEqual(r.campos["ponente"].estado, "discrepante")
        self.assertEqual(r.campos["fecha"].estado, "discrepante")
        self.assertEqual(r.campos["identificador"].estado, "confirmado")

    def test_ratio_solo_en_salvamento(self):
        s, _ = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.verificar_cita("CC", tipo_numero="T-999/99",
                                            ratio_invocada="la tutela era improcedente por existir otro medio de defensa judicial idóneo"))
        self.assertTrue(r.solo_en_salvamento)
        self.assertEqual(r.pasaje.rol, "salvamento")
        self.assertTrue(any("voto separado" in a for a in r.advertencias))

    def test_sentencia_inexistente_es_no_hallada_no_inexistente(self):
        s, _ = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.verificar_cita("CC", tipo_numero="T-123/2005"))
        self.assertEqual(r.estado_global, "no_hallada")
        self.assertIn("ni las rutas directas ni el buscador", r.advertencias[0])

    def test_rechaza_ratio_con_datos_de_partes(self):
        s, falso = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.verificar_cita("CC", tipo_numero="T-999/99", ratio_invocada="accionante Juan Pérez Gómez"))
        self.assertEqual(r.estado_global, "bloqueada")
        self.assertEqual(falso.llamadas, [])  # no salió nada hacia el portal

    def test_lee_por_segmentos_y_usa_corpus(self):
        s, falso = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r0 = self.run_async(s.leer_providencia("CC", "T-999/99", segmento=0, tamano=600))
        self.assertEqual(r0.estado, "ok")
        self.assertGreater(r0.segmento.total, 2)
        r1 = self.run_async(s.leer_providencia("CC", "T-999/99", segmento=r0.segmento.total - 1, tamano=600))
        self.assertEqual(r1.segmento.rol_estimado, "salvamento")
        self.assertEqual(len(falso.llamadas), 1)  # la segunda lectura salió del corpus
        self.assertEqual(r1.documento["canal"], "corpus")

    def test_busqueda_bloqueada_por_privacidad(self):
        s, _ = servicio_con_html(SENTENCIA_SINTETICA, self.URL)
        r = self.run_async(s.buscar_providencia("disciplinado Pedro Pérez López", "CNDJ"))
        self.assertEqual(r.estado, "bloqueada")

    def test_busqueda_sin_navegador_reporta_parcial_no_inexistencia(self):
        s, _ = servicio_con_html("<html><body>portal</body></html>", "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml")
        r = self.run_async(s.buscar_providencia("ilicitud sustancial deber funcional", "CNDJ", 2022, 2026, "rapido"))
        self.assertEqual(r.coverage_status, "insuficiente")
        self.assertIn(r.estado, ("parcial", "portal_no_disponible"))
        self.assertFalse(r.candidatos)

    def test_actualizar_linea_calcula_ventana(self):
        s, _ = servicio_con_html("<html><body>portal</body></html>", "x")
        r = self.run_async(s.actualizar_linea("mora administrativa plazo razonable", "T-999/99", "CC", fecha_corte="2026-10-15"))
        self.assertEqual(r["ventana"], {"desde": 2022, "hasta": 2026, "fecha_corte": "2026-10-15"})
        self.assertEqual(r["sentencia_hito"], "T-999/1999")

    def test_dominio_no_autorizado_bloqueado(self):
        from verificador.http import ClienteHTTP
        c = ClienteHTTP()
        r = self.run_async(c.obtener("https://blog-no-oficial.example.com/sentencia"))
        self.assertEqual(r.estado, "bloqueada")
        self.run_async(c.cerrar())


class TestServidor(unittest.TestCase):
    """Autenticación del servidor ASGI, sin red: se invoca la app directamente."""

    def setUp(self):
        os.environ["MCP_API_KEY"] = "clave-de-prueba"
        import importlib
        import server
        importlib.reload(server)
        self.app = server.app

    def _llamar(self, metodo, ruta, cabeceras=None, cuerpo=b""):
        import asyncio
        estado = {}
        async def receive():
            return {"type": "http.request", "body": cuerpo, "more_body": False}
        async def send(msg):
            if msg["type"] == "http.response.start":
                estado["codigo"] = msg["status"]
        scope = {"type": "http", "method": metodo, "path": ruta, "raw_path": ruta.encode(), "query_string": b"",
                 "headers": [(k.lower().encode(), v.encode()) for k, v in (cabeceras or {}).items()],
                 "scheme": "http", "server": ("test", 80), "client": ("test", 1), "http_version": "1.1"}
        asyncio.get_event_loop().run_until_complete(self.app(scope, receive, send))
        return estado.get("codigo")

    def test_health_sin_llave(self):
        self.assertEqual(self._llamar("GET", "/health"), 200)

    def test_mcp_sin_llave_401(self):
        self.assertEqual(self._llamar("POST", "/mcp", {"content-type": "application/json"}, b"{}"), 401)

    def test_llave_mala_en_ruta_401(self):
        self.assertEqual(self._llamar("POST", "/k/otra/mcp", {"content-type": "application/json"}, b"{}"), 401)

    def test_well_known_404(self):
        self.assertEqual(self._llamar("GET", "/.well-known/oauth-authorization-server"), 404)


if __name__ == "__main__":
    unittest.main()
