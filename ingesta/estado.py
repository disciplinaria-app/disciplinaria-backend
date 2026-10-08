"""
Registro de los correos ya procesados.

La marca de leído del propio buzón IMAP es lo que evita reprocesar; este
registro es un resguardo secundario que además cuenta los intentos fallidos.
Su razón de ser es evitar los dos extremos: reintentar sin fin un correo que
siempre falla, y descartarlo en silencio.
"""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

DIAS_DE_CONSERVACION = 60


class Estado:
    """Registro persistido en un archivo JSON."""

    def __init__(self, ruta: str | Path):
        self.ruta = Path(ruta)
        self._registros: dict[str, dict] = {}
        self._cargar()

    def _cargar(self) -> None:
        if not self.ruta.exists():
            return
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            # Un registro corrupto no debe impedir el arranque: se reconstruye.
            self._registros = {}
            return
        if isinstance(datos, dict) and isinstance(datos.get("procesados"), dict):
            self._registros = datos["procesados"]

    def guardar(self) -> None:
        self._purgar()
        try:
            self.ruta.parent.mkdir(parents=True, exist_ok=True)
            self.ruta.write_text(
                json.dumps({"procesados": self._registros}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )
        except OSError:
            # La pérdida del registro es tolerable; detener el worker, no.
            pass

    def _purgar(self) -> None:
        limite = (date.today() - timedelta(days=DIAS_DE_CONSERVACION)).isoformat()
        self._registros = {
            clave: valor
            for clave, valor in self._registros.items()
            if str(valor.get("fecha", "")) >= limite
        }

    def ya_procesado(self, identificador: str) -> bool:
        registro = self._registros.get(identificador)
        return bool(registro and registro.get("estado") == "procesado")

    def intentos(self, identificador: str) -> int:
        registro = self._registros.get(identificador)
        return int(registro.get("intentos", 0)) if registro else 0

    def registrar_exito(self, identificador: str) -> None:
        if not identificador:
            return
        self._registros[identificador] = {
            "estado": "procesado",
            "fecha": datetime.now().date().isoformat(),
            "intentos": self.intentos(identificador) + 1,
        }

    def registrar_fallo(self, identificador: str, motivo: str) -> int:
        """Anota el intento fallido y devuelve el número acumulado."""
        if not identificador:
            return 0
        intentos = self.intentos(identificador) + 1
        self._registros[identificador] = {
            "estado": "fallido",
            "fecha": datetime.now().date().isoformat(),
            "intentos": intentos,
            "motivo": motivo[:500],
        }
        return intentos
