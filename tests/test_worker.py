"""
Pruebas del worker de ingesta.

El buzón y el servidor de correo se sustituyen por dobles; el agente, por una
función controlada. Lo que se verifica son las garantías del ciclo: que nada se
pierda, que un correo no arrastre a los demás y que ningún fallo quede en
silencio.
"""

import asyncio
from email.message import EmailMessage

import pytest

import config
from agents import agente_triage
from ingesta import worker
from ingesta.estado import Estado
from ingesta.mensaje import CorreoEntrante
from tests.utilidades import construir_pdf_texto

PROPIAS = frozenset({"luis@cendoj.ramajudicial.gov.co"})
PDF = construir_pdf_texto(["LA PREVISORA S.A.", "Respuesta al radicado CNDJ-2025-0412"])

CUERPO_REENVIADO = """#radicado CNDJ-2025-0412

-----Mensaje original-----
De: Notificaciones Previsora <notificaciones@previsora.gov.co>
Enviado: miercoles, 1 de octubre de 2025 10:12 a. m.
Para: Luis Miranda <luis@cendoj.ramajudicial.gov.co>
Asunto: RE: Oficio CNDJ-2025-0412

Esta entidad no es competente; adjunto la devolucion.

De: Luis Miranda
Para: Fiduprevisora S.A.
Asunto: Oficio CNDJ-2025-0412
"""

RESPUESTA_AGENTE = {
    "entidad_remitente": "La Previsora S.A. Compañía de Seguros",
    "tipo_acto": "DEVOLUCION_POR_COMPETENCIA",
    "materia": "La entidad advierte que la comunicación fue dirigida por error.",
    "resumen": "La Previsora informa que el oficio correspondía a Fiduprevisora S.A.",
    "radicados": ["CNDJ-2025-0412"],
    "expedientes": [],
    "requiere_actuacion": True,
    "actuacion_sugerida": "Remitir nuevamente el oficio a Fiduprevisora S.A.",
    "termino": {"fecha_limite": None, "fundamento": None},
    "alertas": [],
    "urgencia": "BAJA",
}


def _reenvio(identificador="<reenvio-1@cendoj>", con_pdf=True) -> bytes:
    correo = EmailMessage()
    correo["From"] = "Luis Miranda <luis@cendoj.ramajudicial.gov.co>"
    correo["To"] = "triage@midominio.com"
    correo["Subject"] = "RV: Oficio CNDJ-2025-0412"
    correo["Message-ID"] = identificador
    correo["Date"] = "Wed, 01 Oct 2025 11:00:00 -0500"
    correo.set_content(CUERPO_REENVIADO)
    if con_pdf:
        correo.add_attachment(
            PDF, maintype="application", subtype="pdf", filename="respuesta.pdf"
        )
    return correo.as_bytes()


class BuzonFalso:
    def __init__(self, mensajes: list[tuple[bytes, bytes]]):
        self.mensajes = mensajes
        self.leidos: list[bytes] = []

    def mensajes_sin_leer(self, limite: int):
        return iter(self.mensajes[:limite])

    def marcar_leido(self, identificador: bytes) -> None:
        self.leidos.append(identificador)


class NotificadorFalso:
    def __init__(self, falla: bool = False):
        self.falla = falla
        self.enviados: list[tuple[str, str]] = []

    def enviar(self, asunto: str, texto: str, cuerpo_html: str | None = None) -> None:
        if self.falla:
            raise ConnectionError("servidor de correo inaccesible")
        self.enviados.append((asunto, texto))


@pytest.fixture
def agente(monkeypatch):
    async def ejecutar(**_kwargs):
        return dict(RESPUESTA_AGENTE), []

    monkeypatch.setattr(agente_triage, "ejecutar", ejecutar)


def _ciclo(buzon, notificador, estado, limite=10):
    return asyncio.run(worker.ejecutar_ciclo(buzon, notificador, estado, limite, PROPIAS))


class TestCicloCompleto:
    def test_clasifica_el_reenvio_y_remite_la_ficha(self, agente, tmp_path):
        """
        Recorrido completo de la ruta: Outlook reenvía, el worker recupera el
        remitente original, extrae el PDF, coteja y remite la ficha.
        """
        buzon = BuzonFalso([(b"101", _reenvio())])
        notificador = NotificadorFalso()
        estado = Estado(tmp_path / "estado.json")

        resumen = _ciclo(buzon, notificador, estado)

        assert (resumen.revisados, resumen.clasificados, resumen.fallidos) == (1, 1, 0)
        assert buzon.leidos == [b"101"]
        assert estado.ya_procesado("<reenvio-1@cendoj>") is True

        asunto, texto = notificador.enviados[0]
        # La discrepancia de entidad es el hallazgo que motiva todo el módulo.
        assert asunto.startswith("[ALTA]")
        assert "ENTIDAD_DISTINTA" in texto
        assert "Fiduprevisora" in texto
        # La directiva #radicado hizo posible el cotejo del radicado.
        assert "CNDJ-2025-0412" in texto

    def test_la_directiva_declarada_alimenta_el_contexto(self):
        entrante = CorreoEntrante(
            identificador="<a@b>",
            remitente="x@y.gov.co",
            asunto="Oficio",
            fecha=None,
            cuerpo="",
            entidad_declarada="Fiduprevisora S.A.",
            radicado_declarado="CNDJ-2025-0412",
            asunto_declarado="Oficio original",
        )
        contexto = worker.construir_contexto(entrante)
        assert contexto.entidad_interpelada == "Fiduprevisora S.A."
        assert contexto.radicado_enviado == "CNDJ-2025-0412"
        assert contexto.asunto_enviado == "Oficio original"

    def test_sin_directivas_el_contexto_queda_para_deducirse(self):
        entrante = CorreoEntrante(
            identificador="<a@b>", remitente="x@y.gov.co", asunto="", fecha=None, cuerpo=""
        )
        contexto = worker.construir_contexto(entrante)
        assert contexto.entidad_interpelada is None
        assert contexto.radicado_enviado is None

    def test_un_correo_ya_procesado_se_omite_sin_volver_a_notificar(self, agente, tmp_path):
        estado = Estado(tmp_path / "estado.json")
        estado.registrar_exito("<reenvio-1@cendoj>")
        buzon = BuzonFalso([(b"101", _reenvio())])
        notificador = NotificadorFalso()

        resumen = _ciclo(buzon, notificador, estado)

        assert resumen.omitidos == 1
        assert notificador.enviados == []
        assert buzon.leidos == [b"101"]

    def test_respeta_el_limite_de_correos_por_ciclo(self, agente, tmp_path):
        mensajes = [
            (str(i).encode(), _reenvio(identificador=f"<reenvio-{i}@cendoj>", con_pdf=False))
            for i in range(5)
        ]
        buzon = BuzonFalso(mensajes)
        resumen = _ciclo(buzon, NotificadorFalso(), Estado(tmp_path / "e.json"), limite=2)
        assert resumen.revisados == 2
        assert len(buzon.leidos) == 2


class TestManejoDeFallos:
    def _forzar_fallo(self, monkeypatch, motivo="TimeoutError"):
        async def fallar(_entrante):
            raise TimeoutError(motivo)

        monkeypatch.setattr(worker, "clasificar", fallar)

    def test_con_reintentos_pendientes_el_correo_se_conserva_sin_leer(
        self, monkeypatch, tmp_path
    ):
        self._forzar_fallo(monkeypatch)
        buzon = BuzonFalso([(b"101", _reenvio())])
        notificador = NotificadorFalso()
        estado = Estado(tmp_path / "estado.json")

        resumen = _ciclo(buzon, notificador, estado)

        assert resumen.fallidos == 1
        assert buzon.leidos == []  # se reintentará en el próximo ciclo
        assert notificador.enviados == []
        assert estado.intentos("<reenvio-1@cendoj>") == 1

    def test_agotados_los_reintentos_se_avisa_y_se_da_por_procesado(
        self, monkeypatch, tmp_path
    ):
        self._forzar_fallo(monkeypatch)
        estado = Estado(tmp_path / "estado.json")
        for _ in range(config.MAX_INTENTOS_POR_CORREO - 1):
            estado.registrar_fallo("<reenvio-1@cendoj>", "previo")

        buzon = BuzonFalso([(b"101", _reenvio())])
        notificador = NotificadorFalso()
        resumen = _ciclo(buzon, notificador, estado)

        assert resumen.fallidos == 1
        assert buzon.leidos == [b"101"]
        asunto, texto = notificador.enviados[0]
        assert "No se pudo clasificar" in asunto
        assert "correspondencia pendiente" in texto

    def test_si_tampoco_se_puede_avisar_el_correo_no_se_marca_como_leido(
        self, monkeypatch, tmp_path
    ):
        """
        Darlo por procesado sin que el usuario lo sepa equivaldría a perder
        correspondencia, que es lo único inadmisible en esta ruta.
        """
        self._forzar_fallo(monkeypatch)
        estado = Estado(tmp_path / "estado.json")
        for _ in range(config.MAX_INTENTOS_POR_CORREO):
            estado.registrar_fallo("<reenvio-1@cendoj>", "previo")

        buzon = BuzonFalso([(b"101", _reenvio())])
        resumen = _ciclo(buzon, NotificadorFalso(falla=True), estado)

        assert resumen.fallidos == 1
        assert buzon.leidos == []
        assert estado.ya_procesado("<reenvio-1@cendoj>") is False

    def test_el_fallo_de_un_correo_no_arrastra_a_los_demas(self, agente, tmp_path):
        class NotificadorQueFallaLaPrimeraVez(NotificadorFalso):
            def __init__(self):
                super().__init__()
                self.llamadas = 0

            def enviar(self, asunto, texto, cuerpo_html=None):
                self.llamadas += 1
                if self.llamadas == 1:
                    raise ConnectionError("fallo transitorio")
                self.enviados.append((asunto, texto))

        buzon = BuzonFalso(
            [
                (b"101", _reenvio(identificador="<reenvio-1@cendoj>")),
                (b"102", _reenvio(identificador="<reenvio-2@cendoj>")),
            ]
        )
        notificador = NotificadorQueFallaLaPrimeraVez()
        resumen = _ciclo(buzon, notificador, Estado(tmp_path / "estado.json"))

        assert resumen.revisados == 2
        assert resumen.clasificados == 1
        assert resumen.fallidos == 1
        # El primero conserva su reintento; el segundo se procesó con normalidad.
        assert buzon.leidos == [b"102"]
        assert len(notificador.enviados) == 1

    def test_un_mensaje_corrupto_se_notifica_en_lugar_de_descartarse(self, agente, tmp_path):
        """
        El analizador MIME de la biblioteca estándar es tolerante y no lanza
        excepción ante bytes corruptos: produce un mensaje de encabezados
        vacíos. El worker lo clasifica y lo notifica igual, lo que es preferible
        a descartar correspondencia que podría ser legítima.
        """
        buzon = BuzonFalso([(b"101", b"esto no es un mensaje MIME valido \xff\xfe")])
        notificador = NotificadorFalso()
        resumen = _ciclo(buzon, notificador, Estado(tmp_path / "estado.json"))

        assert resumen.revisados == 1
        assert resumen.fallidos == 0
        assert len(notificador.enviados) == 1
        assert buzon.leidos == [b"101"]

    def test_el_fallo_al_marcar_como_leido_no_detiene_el_ciclo(self, agente, tmp_path):
        class BuzonQueFallaAlMarcar(BuzonFalso):
            def marcar_leido(self, identificador):
                raise ConnectionError("conexión perdida")

        buzon = BuzonQueFallaAlMarcar([(b"101", _reenvio())])
        resumen = _ciclo(buzon, NotificadorFalso(), Estado(tmp_path / "e.json"))
        assert resumen.clasificados == 1


class TestVerificacionDeConfiguracion:
    def test_enumera_lo_que_falta_antes_de_intentar_conectarse(self, monkeypatch):
        monkeypatch.setattr(config, "OPENROUTER_API_KEY", "")
        monkeypatch.setattr(config, "IMAP_SERVIDOR", "")
        monkeypatch.setattr(config, "SMTP_SERVIDOR", "")
        faltantes = worker.verificar_configuracion()
        assert any("OPENROUTER_API_KEY" in f for f in faltantes)
        assert any("IMAP_SERVIDOR" in f for f in faltantes)
        assert any("SMTP_SERVIDOR" in f for f in faltantes)

    def test_configuracion_completa_no_reporta_faltantes(self, monkeypatch):
        for nombre, valor in {
            "OPENROUTER_API_KEY": "clave",
            "IMAP_SERVIDOR": "imap.ejemplo.com",
            "IMAP_USUARIO": "buzon@ejemplo.com",
            "IMAP_CLAVE": "clave",
            "SMTP_SERVIDOR": "smtp.ejemplo.com",
            "SMTP_REMITENTE": "buzon@ejemplo.com",
            "DESTINATARIO_FICHAS": "luis@cendoj.ramajudicial.gov.co",
        }.items():
            monkeypatch.setattr(config, nombre, valor)
        assert worker.verificar_configuracion() == []

    def test_el_programa_termina_con_codigo_2_si_falta_configuracion(self, monkeypatch, capsys):
        monkeypatch.setattr(worker, "verificar_configuracion", lambda: ["IMAP_SERVIDOR"])
        assert worker.main(["--una-vez"]) == 2
        assert "Falta configurar" in capsys.readouterr().err

    def test_el_ciclo_unico_informa_el_resumen(self, monkeypatch, capsys):
        monkeypatch.setattr(worker, "verificar_configuracion", lambda: [])
        monkeypatch.setattr(worker, "un_ciclo", lambda limite: worker.Resumen(revisados=2, clasificados=2))
        assert worker.main(["--una-vez"]) == 0
        assert "clasificados=2" in capsys.readouterr().out

    def test_un_fallo_del_ciclo_unico_devuelve_codigo_1(self, monkeypatch, capsys):
        monkeypatch.setattr(worker, "verificar_configuracion", lambda: [])

        def fallar(_limite):
            raise ConnectionError("imap inaccesible")

        monkeypatch.setattr(worker, "un_ciclo", fallar)
        assert worker.main(["--una-vez"]) == 1
        assert "imap inaccesible" in capsys.readouterr().err


class TestBucleDeRealimentacion:
    def test_una_ficha_del_propio_sistema_no_se_clasifica(self, agente, tmp_path):
        """
        Por omisión el buzón de fichas es el mismo de ingesta. Sin esta
        salvaguarda la ficha volvería al buzón, se clasificaría a sí misma y el
        ciclo se realimentaría sin término.
        """
        from ingesta.mensaje import CABECERA_SISTEMA

        ficha = EmailMessage()
        ficha["From"] = "triage@midominio.com"
        ficha["To"] = "triage@midominio.com"
        ficha["Subject"] = "[ALTA] La Previsora · Devolucion Por Competencia"
        ficha["Message-ID"] = "<ficha-1@midominio>"
        ficha[CABECERA_SISTEMA] = "ficha"
        ficha.set_content("ALERTAS\n  ● [ALTA] ENTIDAD_DISTINTA: ...")

        buzon = BuzonFalso([(b"201", ficha.as_bytes())])
        notificador = NotificadorFalso()
        resumen = _ciclo(buzon, notificador, Estado(tmp_path / "estado.json"))

        assert resumen.omitidos == 1
        assert resumen.clasificados == 0
        assert notificador.enviados == []
        assert buzon.leidos == [b"201"]

    def test_la_ficha_remitida_lleva_la_marca_del_sistema(self, monkeypatch):
        """Verifica el otro extremo: que la marca se escriba al enviar."""
        from ingesta import notificacion as envio
        from ingesta.mensaje import CABECERA_SISTEMA

        enviados = []

        class SesionFalsa:
            def __init__(self, *_a, **_k):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_a):
                return False

            def starttls(self):
                pass

            def login(self, *_a):
                pass

            def send_message(self, correo):
                enviados.append(correo)

        monkeypatch.setattr(envio.smtplib, "SMTP", SesionFalsa)
        notificador = envio.NotificadorSMTP(
            envio.ConfiguracionSMTP(
                servidor="smtp.ejemplo.com",
                usuario="buzon@ejemplo.com",
                clave="clave",
                remitente="buzon@ejemplo.com",
                destinatario="buzon@ejemplo.com",
            )
        )
        notificador.enviar("asunto", "texto")

        assert enviados[0][CABECERA_SISTEMA] == "ficha"
