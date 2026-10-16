#!/usr/bin/env python3
"""Auditor local de consistencia declarada. No verifica derecho ni fuentes en red.

Python 3.10+, biblioteca estandar. Salida 0: sin inconsistencias estructurales
identificadas; 1: bloqueos detectados; 2: entrada o ejecucion invalida.
Un resultado 0 NO certifica correccion juridica, autenticidad ni completitud real.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

GROUPS = ('piezas', 'hechos', 'normas', 'citas', 'argumentos', 'problemas',
          'determinaciones', 'apartados')
FIELDS = ('corporacion', 'sala', 'ponente', 'identificador', 'fecha')
LIMIT = 8 * 1024 * 1024
MARKERS = re.compile(
    r'\[(?:VERIFICAR|PENDIENTE|COMPLETAR|REVISAR|CONFIRMAR|CITA)(?::[^\]]*)?\]'
    r'|\[[^\]]{0,120}?(?:no encontr|falta cita|sin soporte|verificar)[^\]]{0,120}\]'
    r'|\b(?:TODO|TBD|XXX)\b|\?\?\?|\bT-xxx\b|\b20xx\b|Rad\.\s*_{2,}',
    re.I)
DISCLAIMER = ('Control estructural sobre datos declarados y texto suministrado. '
              'No verifica autenticidad, verdad, calidad de la prueba, vigencia, '
              'ratio, exhaustividad del expediente ni suficiencia juridica.')


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def is_url(value: Any) -> bool:
    if not nonempty(value):
        return False
    parsed = urlparse(value)
    return parsed.scheme in ('https', 'http') and bool(parsed.netloc)


def is_date(value: Any) -> bool:
    try:
        return isinstance(value, str) and len(value) == 10 and date.fromisoformat(value) <= date.today()
    except ValueError:
        return False


def audit(data: Any, final_text: str | None = None,
          original_text: str | None = None) -> dict[str, Any]:
    issues: list[dict[str, str]] = []

    def fail(code: str, location: str, detail: str) -> None:
        issues.append({'codigo': code, 'ubicacion': location, 'detalle': detail})

    def require_text(row: dict, keys: tuple[str, ...], loc: str) -> None:
        for key in keys:
            if not nonempty(row.get(key)):
                fail('CAMPO_VACIO', f'{loc}.{key}', 'Se requiere texto no vacio.')

    def result() -> dict:
        return {'estado': 'BLOQUEOS_ESTRUCTURALES' if issues else 'SIN_BLOQUEOS_ESTRUCTURALES_DETECTADOS',
                'numero_bloqueos': len(issues), 'hallazgos': issues,
                'sha256_texto_final': hashlib.sha256(final_text.encode('utf-8')).hexdigest()
                if isinstance(final_text, str) else None,
                'limite': DISCLAIMER}

    if not isinstance(data, dict):
        fail('ESQUEMA', '$', 'La raiz debe ser un objeto JSON.'); return result()
    if data.get('esquema') != 1 or isinstance(data.get('esquema'), bool):
        fail('ESQUEMA', 'esquema', 'Se requiere version 1.')
    require_text(data, ('caso_id',), '$')
    if data.get('modo') not in ('integral', 'delimitado', 'editorial', 'auditoria'):
        fail('MODO', 'modo', 'Modo no reconocido.')
    if not isinstance(data.get('cierre_solicitado'), bool):
        fail('ESQUEMA', 'cierre_solicitado', 'Se requiere booleano.')
    if not is_date(data.get('fecha_control')):
        fail('FECHA', 'fecha_control', 'Fecha ISO real, no futura.')
    coverage = data.get('revision_cobertura', {})
    if not isinstance(coverage, dict):
        coverage = {}
    if coverage.get('comprobada') is not True or not nonempty(coverage.get('evidencia')):
        fail('COBERTURA', 'revision_cobertura', 'Falta revision de cobertura declarada y localizada.')

    indexes: dict[str, dict[str, dict]] = {}
    all_ids: set[str] = set()
    for group in GROUPS:
        rows = data.get(group)
        index: dict[str, dict] = {}
        if not isinstance(rows, list):
            fail('ESQUEMA', group, 'Se requiere una lista, aunque no aplique contenido.'); rows = []
        for n, row in enumerate(rows):
            loc = f'{group}[{n}]'
            if not isinstance(row, dict) or not nonempty(row.get('id')):
                fail('ID', loc, 'Cada registro requiere id textual.'); continue
            identifier = row['id']
            if identifier in all_ids:
                fail('ID_DUPLICADO', loc, identifier)
            all_ids.add(identifier); index[identifier] = row
        indexes[group] = index

    scope = data.get('alcance')
    if not isinstance(scope, dict):
        fail('ALCANCE', 'alcance', 'Falta inventario esperado.'); scope = {}
    for group in GROUPS:
        expected = scope.get(group)
        if not isinstance(expected, list) or any(not nonempty(x) for x in expected):
            fail('ALCANCE', f'alcance.{group}', 'Se requiere lista de ids esperados.'); expected = []
        if len(expected) != len(set(expected)):
            fail('ALCANCE_DUPLICADO', f'alcance.{group}', 'Ids repetidos.')
        for identifier in expected:
            if identifier not in indexes[group]:
                fail('OMISION', f'alcance.{group}', f'Falta el registro {identifier}.')
        # Extra records must be deliberately accounted for in the scope, not hidden.
        for identifier in indexes[group]:
            if identifier not in expected:
                fail('FUERA_DE_INVENTARIO', group, identifier)
    if data.get('modo') == 'integral' and data.get('cierre_solicitado') is True:
        for group in ('piezas', 'problemas', 'determinaciones', 'apartados'):
            if not indexes[group]:
                fail('INTEGRAL_VACIO', group, 'Un cierre integral requiere registros en este grupo.')

    def references(row: dict, key: str, target: str, loc: str,
                   required: bool = False) -> list[str]:
        values = row.get(key)
        if not isinstance(values, list) or any(not nonempty(x) for x in values):
            fail('REFERENCIA', f'{loc}.{key}', 'Se requiere lista de ids.'); return []
        if required and not values:
            fail('REFERENCIA_VACIA', f'{loc}.{key}', 'Falta vinculo necesario.')
        for identifier in values:
            if identifier not in indexes[target]:
                fail('REFERENCIA_ROTA', f'{loc}.{key}', identifier)
        return values

    for identifier, row in indexes['piezas'].items():
        require_text(row, ('localizador', 'estado_lectura'), identifier)
        if not isinstance(row.get('esencial'), bool):
            fail('ESQUEMA', identifier, 'esencial debe ser booleano.')
        if row.get('esencial') is True and row.get('estado_lectura') != 'completa':
            if not (row.get('faltante_resoluble') is True and nonempty(row.get('fundamento_faltante'))):
                fail('LECTURA_INCOMPLETA', identifier, 'Pieza esencial sin lectura completa ni tratamiento fundado del faltante.')
        if row.get('estado_lectura') == 'completa' and row.get('segmentos_pendientes') != []:
            fail('LECTURA_CONTRADICTORIA', identifier, 'Lectura completa requiere segmentos_pendientes vacio.')

    for identifier, row in indexes['hechos'].items():
        require_text(row, ('enunciado', 'clasificacion', 'valoracion'), identifier)
        if row.get('clasificacion') not in ('alegado', 'acreditado', 'controvertido', 'inferido', 'no_acreditado'):
            fail('HECHO_CLASE', identifier, 'Clasificacion no reconocida.')
        refs = references(row, 'piezas', 'piezas', identifier)
        if row.get('premisa_decisiva') is True:
            if not refs or not nonempty(row.get('localizador_fuente')):
                fail('HECHO_SIN_SOPORTE', identifier, 'Premisa decisiva sin fuente localizada.')
            if row.get('clasificacion') == 'alegado':
                fail('ALEGACION_COMO_PRUEBA', identifier, 'Una alegacion no basta como hecho decisivo acreditado.')
        if row.get('clasificacion') == 'inferido':
            bases = references(row, 'hechos_base', 'hechos', identifier, required=True)
            require_text(row, ('regla_inferencia',), identifier)
            if identifier in bases:
                fail('INFERENCIA_CIRCULAR', identifier, 'El hecho es su propia base.')

    # Detect cycles between declared inferential bases.
    done: set[str] = set(); active: set[str] = set()
    def visit(identifier: str) -> None:
        if identifier in active:
            fail('INFERENCIA_CIRCULAR', identifier, 'Ciclo entre hechos inferidos.'); return
        if identifier in done:
            return
        active.add(identifier)
        bases = indexes['hechos'].get(identifier, {}).get('hechos_base', [])
        if isinstance(bases, list):
            for base in bases:
                if isinstance(base, str) and base in indexes['hechos']:
                    visit(base)
        active.remove(identifier); done.add(identifier)
    for identifier in indexes['hechos']:
        visit(identifier)

    for identifier, row in indexes['normas'].items():
        require_text(row, ('identificacion', 'version_aplicable', 'localizador', 'aplicacion_caso'), identifier)
        if not is_url(row.get('url_oficial')) or not is_date(row.get('consultada_en')):
            fail('FUENTE_NORMA', identifier, 'URL o fecha de consulta no declaradas correctamente.')
        if row.get('control_temporal') != 'verificado':
            fail('NORMA_TEMPORAL', identifier, 'Aplicacion temporal no verificada.')

    for identifier, row in indexes['citas'].items():
        require_text(row, ('pasaje', 'localizador', 'justificacion_aplicabilidad'), identifier)
        if not is_url(row.get('url_oficial')) or not is_date(row.get('consultada_en')):
            fail('FUENTE_CITA', identifier, 'URL o fecha de consulta no declaradas correctamente.')
        if row.get('origen') != 'fuente_oficial':
            fail('ORIGEN_CITA', identifier, 'La identidad no puede confirmarse por origen generativo o secundario.')
        metadata = row.get('datos')
        if not isinstance(metadata, dict): metadata = {}
        for field in FIELDS:
            item = metadata.get(field, {})
            if not isinstance(item, dict): item = {}
            if item.get('estado') == 'no_aplica':
                if field in ('corporacion', 'identificador', 'fecha'):
                    fail('METADATO_ESENCIAL', f'{identifier}.{field}', 'Dato esencial no puede declararse no aplicable.')
                if not nonempty(item.get('justificacion')):
                    fail('METADATO', f'{identifier}.{field}', 'No aplica sin justificacion.')
            elif item.get('estado') != 'confirmado' or not nonempty(item.get('valor')):
                fail('METADATO', f'{identifier}.{field}', 'Dato no confirmado o vacio.')
            if not nonempty(item.get('evidencia')) or not nonempty(item.get('localizador')):
                fail('METADATO_EVIDENCIA', f'{identifier}.{field}', 'Falta evidencia localizada.')
        if row.get('estado_identidad') != 'confirmada':
            fail('IDENTIDAD', identifier, 'Identidad pendiente.')
        if row.get('uso') not in ('fundamento', 'contraste_identificado'):
            fail('USO_CITA', identifier, 'Uso no reconocido.')
        if row.get('uso') == 'fundamento' and (row.get('seccion') not in ('razones_mayoria', 'resolutiva')
                                              or row.get('solo_en_salvamento') is True):
            fail('ATRIBUCION', identifier, 'No atribuir a la mayoria tesis de otra voz.')
        if row.get('ratio_estado') != 'verificada' or row.get('aplicabilidad') != 'verificada':
            fail('RATIO_APLICABILIDAD', identifier, 'Identidad no sustituye examen de ratio y pertinencia.')
        update = row.get('actualizacion', {})
        if not isinstance(update, dict): update = {}
        if update.get('estado') != 'realizada' or not nonempty(update.get('evidencia')):
            fail('ACTUALIZACION', identifier, 'Falta busqueda de actualidad documentada.')

    for identifier, row in indexes['argumentos'].items():
        require_text(row, ('tesis', 'respuesta', 'localizador_respuesta'), identifier)
        references(row, 'problemas', 'problemas', identifier, required=True)
        if row.get('estado') not in ('respondido', 'absorbido', 'no_abordable_fundado'):
            fail('ARGUMENTO_PENDIENTE', identifier, 'Argumento sin respuesta juridica localizada.')
        if row.get('estado') == 'absorbido':
            target = row.get('absorbido_por')
            if not isinstance(target, str) or target not in indexes['argumentos'] or target == identifier:
                fail('ABSORCION', identifier, 'Absorcion sin argumento distinto identificado.')
    # Absorption cannot form a chain that never reaches an answered argument.
    for identifier in indexes['argumentos']:
        visited: set[str] = set()
        current = identifier
        while current in indexes['argumentos']:
            if current in visited:
                fail('ABSORCION_CIRCULAR', identifier, 'Ciclo entre argumentos absorbidos.')
                break
            visited.add(current)
            argument = indexes['argumentos'][current]
            if argument.get('estado') != 'absorbido':
                break
            target = argument.get('absorbido_por')
            if not isinstance(target, str):
                break
            current = target
    for identifier, row in indexes['problemas'].items():
        require_text(row, ('pregunta', 'conclusion', 'localizador'), identifier)
        if row.get('estado') not in ('resuelto', 'no_abordable_fundado'):
            fail('PROBLEMA_PENDIENTE', identifier, 'Problema pendiente.')
        references(row, 'hechos', 'hechos', identifier)
        references(row, 'normas', 'normas', identifier)
        references(row, 'citas', 'citas', identifier)
        decisions = references(row, 'determinaciones', 'determinaciones', identifier,
                               required=row.get('requiere_decision') is True)
        for d in decisions:
            if identifier not in indexes['determinaciones'].get(d, {}).get('problemas', []):
                fail('CONGRUENCIA_ENLACE', identifier, f'La determinacion {d} no corresponde reciprocamente.')
    for identifier, row in indexes['determinaciones'].items():
        require_text(row, ('texto', 'fundamento_localizador', 'tipo'), identifier)
        problems = references(row, 'problemas', 'problemas', identifier, required=True)
        for p in problems:
            if identifier not in indexes['problemas'].get(p, {}).get('determinaciones', []):
                fail('CONGRUENCIA_ENLACE', identifier, f'Problema {p} sin determinacion reciproca.')
        if row.get('tipo') == 'orden':
            require_text(row, ('destinatario', 'conducta'), identifier)
            if not nonempty(row.get('plazo')) and not nonempty(row.get('plazo_no_aplica')):
                fail('ORDEN_PLAZO', identifier, 'Plazo no definido ni inaplicabilidad justificada.')
    for identifier, row in indexes['apartados'].items():
        require_text(row, ('titulo', 'localizador'), identifier)
        if row.get('estado') != 'completo':
            fail('APARTADO_PENDIENTE', identifier, 'Apartado no completado.')

    for group in ('hallazgos', 'protecciones', 'cambios_verificados'):
        if not isinstance(data.get(group), list):
            fail('ESQUEMA', group, 'Se requiere lista.'); continue
        for n, row in enumerate(data[group]):
            if not isinstance(row, dict):
                fail('ESQUEMA', f'{group}[{n}]', 'Registro no es objeto.'); continue
            loc = f'{group}[{n}]'
            if group == 'hallazgos':
                if row.get('severidad') in ('bloqueante', 'sustancial') and row.get('estado') != 'resuelto':
                    fail('HALLAZGO_ABIERTO', loc, 'Hallazgo sustancial o bloqueante pendiente.')
                if row.get('estado') == 'resuelto' and not nonempty(row.get('evidencia_cierre')):
                    fail('HALLAZGO_SIN_EVIDENCIA', loc, 'Cierre sin evidencia.')
            elif group == 'protecciones':
                value = row.get('texto'); minimum = row.get('minimo')
                if not nonempty(value) or type(minimum) is not int or minimum < 1:
                    fail('PROTECCION', loc, 'Texto y minimo entero positivo requeridos.'); continue
                if original_text is None:
                    fail('ORIGINAL_FALTANTE', loc, 'Se requiere texto original para contraste protegido.')
                elif original_text.count(value) < minimum:
                    fail('PROTECCION_ORIGEN', loc, 'La cadena declarada no consta suficientes veces en el original.')
                if final_text is None or final_text.count(value) < minimum:
                    fail('INTEGRIDAD_LITERAL', loc, 'Cadena protegida ausente o alterada en el resultado.')
            else:
                require_text(row, ('original', 'corregido', 'fuente', 'localizador', 'razon'), loc)
                if row.get('reportado') is not True:
                    fail('CAMBIO_NO_REPORTADO', loc, 'Correccion sustancial sin reporte.')
                if nonempty(row.get('original')) and (original_text is None or row['original'] not in original_text):
                    fail('CAMBIO_ORIGEN', loc, 'Original del cambio no localizado.')
                if nonempty(row.get('corregido')) and (final_text is None or row['corregido'] not in final_text):
                    fail('CAMBIO_DESTINO', loc, 'Correccion declarada no localizada.')

    gates = data.get('puertas')
    if not isinstance(gates, dict): gates = {}
    for number in range(8):
        key = f'G{number}'; gate = gates.get(key, {})
        if not isinstance(gate, dict): gate = {}
        if gate.get('estado') not in ('superada', 'no_aplica') or not nonempty(gate.get('evidencia')):
            fail('PUERTA_ABIERTA', key, 'Control pendiente o sin evidencia declarada.')
    delivery = data.get('entrega', {})
    if not isinstance(delivery, dict): delivery = {}
    require_text(delivery, ('medio', 'referencia'), 'entrega')
    if delivery.get('relectura_confirmada') is not True:
        fail('RELECTURA', 'entrega', 'Entrega sin lectura posterior confirmada.')
    if delivery.get('edicion_afirmada') is True and delivery.get('escritura_confirmada') is not True:
        fail('ESCRITURA', 'entrega', 'Edicion afirmada sin escritura confirmada.')
    if data.get('cierre_solicitado') is True and not nonempty(final_text):
        fail('TEXTO_FINAL', 'entrega', 'No se puede cerrar sin texto final no vacio.')
    if isinstance(final_text, str):
        for match in MARKERS.finditer(final_text):
            fail('MARCADOR_PENDIENTE', f'texto:{match.start()}', match.group(0))
        expected_hash = delivery.get('sha256_texto_final')
        if expected_hash is not None and expected_hash != hashlib.sha256(final_text.encode('utf-8')).hexdigest():
            fail('VERSION_TEXTO', 'entrega.sha256_texto_final', 'El hash corresponde a otra version.')
    return result()


def read_small(path: Path) -> str:
    if path.stat().st_size > LIMIT:
        raise ValueError(f'Archivo excede limite local de {LIMIT} bytes: {path.name}')
    return path.read_text(encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('control', type=Path)
    parser.add_argument('--texto-final', type=Path)
    parser.add_argument('--texto-original', type=Path)
    parser.add_argument('--reporte', type=Path)
    args = parser.parse_args()
    try:
        # Do not permit a report path to overwrite an input.
        inputs = [p.resolve() for p in (args.control, args.texto_final, args.texto_original) if p]
        if args.reporte and args.reporte.resolve() in inputs:
            raise ValueError('El reporte no puede sobrescribir una entrada.')
        data = json.loads(read_small(args.control))
        final = read_small(args.texto_final) if args.texto_final else None
        original = read_small(args.texto_original) if args.texto_original else None
        report = audit(data, final, original)
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
        if args.reporte:
            args.reporte.parent.mkdir(parents=True, exist_ok=True)
            args.reporte.write_text(encoded, encoding='utf-8')
        print(encoded, end='')
        return 1 if report['numero_bloqueos'] else 0
    except (OSError, ValueError, TypeError, RecursionError) as exc:
        print(json.dumps({'estado': 'ENTRADA_INVALIDA', 'detalle': str(exc),
                          'limite': DISCLAIMER}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
