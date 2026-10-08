"""Pruebas del registro de correos procesados."""

import json

from ingesta.estado import DIAS_DE_CONSERVACION, Estado


class TestRegistro:
    def test_registra_el_exito_y_lo_persiste(self, tmp_path):
        ruta = tmp_path / "estado.json"
        estado = Estado(ruta)
        assert estado.ya_procesado("<a@b>") is False
        estado.registrar_exito("<a@b>")
        estado.guardar()

        reabierto = Estado(ruta)
        assert reabierto.ya_procesado("<a@b>") is True

    def test_cuenta_los_intentos_fallidos(self, tmp_path):
        estado = Estado(tmp_path / "estado.json")
        assert estado.registrar_fallo("<a@b>", "TimeoutError") == 1
        assert estado.registrar_fallo("<a@b>", "TimeoutError") == 2
        assert estado.intentos("<a@b>") == 2
        # Un correo fallido no está procesado: debe reintentarse.
        assert estado.ya_procesado("<a@b>") is False

    def test_un_identificador_vacio_no_se_registra(self, tmp_path):
        estado = Estado(tmp_path / "estado.json")
        estado.registrar_exito("")
        assert estado.registrar_fallo("", "motivo") == 0
        assert estado.ya_procesado("") is False

    def test_el_motivo_se_recorta(self, tmp_path):
        estado = Estado(tmp_path / "estado.json")
        estado.registrar_fallo("<a@b>", "x" * 2000)
        estado.guardar()
        datos = json.loads((tmp_path / "estado.json").read_text(encoding="utf-8"))
        assert len(datos["procesados"]["<a@b>"]["motivo"]) == 500


class TestTolerancia:
    def test_un_archivo_corrupto_no_impide_el_arranque(self, tmp_path):
        ruta = tmp_path / "estado.json"
        ruta.write_text("{ esto no es json", encoding="utf-8")
        estado = Estado(ruta)
        assert estado.ya_procesado("<a@b>") is False
        estado.registrar_exito("<a@b>")
        estado.guardar()
        assert Estado(ruta).ya_procesado("<a@b>") is True

    def test_un_archivo_con_estructura_inesperada_se_ignora(self, tmp_path):
        ruta = tmp_path / "estado.json"
        ruta.write_text('["una", "lista"]', encoding="utf-8")
        assert Estado(ruta).ya_procesado("<a@b>") is False

    def test_crea_el_directorio_si_no_existe(self, tmp_path):
        estado = Estado(tmp_path / "sub" / "dir" / "estado.json")
        estado.registrar_exito("<a@b>")
        estado.guardar()
        assert (tmp_path / "sub" / "dir" / "estado.json").exists()


class TestPurga:
    def test_descarta_los_registros_antiguos_al_guardar(self, tmp_path):
        from datetime import date, timedelta

        ruta = tmp_path / "estado.json"
        antiguo = (date.today() - timedelta(days=DIAS_DE_CONSERVACION + 5)).isoformat()
        ruta.write_text(
            json.dumps(
                {
                    "procesados": {
                        "<viejo@b>": {"estado": "procesado", "fecha": antiguo, "intentos": 1},
                        "<nuevo@b>": {
                            "estado": "procesado",
                            "fecha": date.today().isoformat(),
                            "intentos": 1,
                        },
                    }
                }
            ),
            encoding="utf-8",
        )
        estado = Estado(ruta)
        estado.guardar()

        datos = json.loads(ruta.read_text(encoding="utf-8"))
        assert "<viejo@b>" not in datos["procesados"]
        assert "<nuevo@b>" in datos["procesados"]
