"""Pruebas sinteticas del auditor estructural; no son casos ni citas reales."""
from __future__ import annotations
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('auditor', ROOT / 'scripts/auditar_entrega.py')
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(module)
audit = module.audit
FINAL = 'TEXTO SINTETICO. Dato protegido. Consideraciones y resolutiva de prueba.'


def fixture() -> dict:
    data = {
        'esquema': 1, 'caso_id': 'CASO_SINTETICO_NO_JUDICIAL',
        'modo': 'integral', 'fecha_control': '2020-01-01', 'cierre_solicitado': True,
        'revision_cobertura': {'comprobada': True, 'evidencia': 'Inventario sintetico revisado.'},
        'piezas': [{'id': 'P1', 'localizador': 'insumo-sintetico:1', 'esencial': True,
                    'estado_lectura': 'completa', 'segmentos_pendientes': []}],
        'hechos': [{'id': 'H1', 'enunciado': 'Hecho inventado solo para probar software.',
                    'clasificacion': 'acreditado', 'valoracion': 'No es evidencia judicial.',
                    'piezas': ['P1'], 'premisa_decisiva': True, 'localizador_fuente': 'p.1'}],
        'normas': [{'id': 'N1', 'identificacion': 'NORMA_SINTETICA_NO_REAL',
                    'version_aplicable': 'Version sintetica', 'control_temporal': 'verificado',
                    'url_oficial': 'https://fuente.invalid/norma', 'consultada_en': '2020-01-01',
                    'localizador': 'parrafo de prueba', 'aplicacion_caso': 'Solo prueba de estructura.'}],
        'citas': [{'id': 'J1', 'estado_identidad': 'confirmada', 'origen': 'fuente_oficial',
                   'url_oficial': 'https://fuente.invalid/decision', 'consultada_en': '2020-01-01',
                   'pasaje': 'Pasaje sintetico, no atribuible a tribunal alguno.',
                   'localizador': 'p.1', 'justificacion_aplicabilidad': 'No es aplicabilidad juridica real.',
                   'uso': 'fundamento', 'seccion': 'razones_mayoria', 'solo_en_salvamento': False,
                   'ratio_estado': 'verificada', 'aplicabilidad': 'verificada',
                   'actualizacion': {'estado': 'realizada', 'evidencia': 'Registro sintetico.'},
                   'datos': {field: {'estado': 'confirmado', 'valor': 'DATO_SINTETICO',
                                     'evidencia': 'Evidencia simulada para prueba de codigo.',
                                     'localizador': 'p.1'} for field in module.FIELDS}}],
        'argumentos': [{'id': 'A1', 'tesis': 'Tesis sintetica.', 'estado': 'respondido',
                       'respuesta': 'Respuesta sintetica.', 'localizador_respuesta': 'seccion de prueba',
                       'problemas': ['Q1']}],
        'problemas': [{'id': 'Q1', 'pregunta': 'Pregunta sintetica?', 'conclusion': 'Conclusion de prueba.',
                      'localizador': 'consideraciones de prueba', 'estado': 'resuelto',
                      'hechos': ['H1'], 'normas': ['N1'], 'citas': ['J1'],
                      'requiere_decision': True, 'determinaciones': ['D1']}],
        'determinaciones': [{'id': 'D1', 'texto': 'Determinacion de prueba.',
                            'fundamento_localizador': 'consideraciones de prueba', 'tipo': 'declaracion',
                            'problemas': ['Q1']}],
        'apartados': [{'id': 'S1', 'titulo': 'Seccion sintetica.', 'estado': 'completo', 'localizador': 'p.1'}],
        'protecciones': [{'texto': 'Dato protegido.', 'minimo': 1}],
        'cambios_verificados': [], 'hallazgos': [],
        'puertas': {f'G{i}': {'estado': 'superada', 'evidencia': 'Evidencia sintetica de prueba.'}
                    for i in range(8)},
        'entrega': {'medio': 'texto', 'referencia': 'texto de prueba', 'relectura_confirmada': True,
                    'edicion_afirmada': False, 'escritura_confirmada': False},
    }
    data['alcance'] = {group: [row['id'] for row in data[group]] for group in module.GROUPS}
    return data


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.data = fixture()

    def codes(self, final=FINAL, original=FINAL):
        return {x['codigo'] for x in audit(self.data, final, original)['hallazgos']}

    def test_01_fixture_structure_only(self):
        r = audit(self.data, FINAL, FINAL)
        self.assertEqual(r['numero_bloqueos'], 0)
        self.assertIn('No verifica autenticidad', r['limite'])

    def test_02_empty_input_fails(self):
        self.assertGreater(audit({}, FINAL, FINAL)['numero_bloqueos'], 0)

    def test_03_non_object_fails(self):
        self.assertIn('ESQUEMA', {x['codigo'] for x in audit([])['hallazgos']})

    def test_04_missing_expected_argument(self):
        self.data['alcance']['argumentos'].append('A2')
        self.assertIn('OMISION', self.codes())

    def test_05_duplicate_id(self):
        self.data['piezas'].append(copy.deepcopy(self.data['piezas'][0]))
        self.assertIn('ID_DUPLICADO', self.codes())

    def test_06_incomplete_essential(self):
        self.data['piezas'][0]['estado_lectura'] = 'parcial'
        self.assertIn('LECTURA_INCOMPLETA', self.codes())

    def test_07_incomplete_but_treated_with_reason(self):
        p = self.data['piezas'][0]
        p.update(estado_lectura='no_accesible', faltante_resoluble=True,
                 fundamento_faltante='Tratamiento juridico declarado solo para prueba.')
        self.assertNotIn('LECTURA_INCOMPLETA', self.codes())

    def test_08_declared_complete_with_pending_ranges(self):
        self.data['piezas'][0]['segmentos_pendientes'] = ['p.2']
        self.assertIn('LECTURA_CONTRADICTORIA', self.codes())

    def test_09_fact_without_support(self):
        self.data['hechos'][0]['piezas'] = []
        self.assertIn('HECHO_SIN_SOPORTE', self.codes())

    def test_10_allegation_as_proven_fact(self):
        self.data['hechos'][0]['clasificacion'] = 'alegado'
        self.assertIn('ALEGACION_COMO_PRUEBA', self.codes())

    def test_11_self_supporting_inference(self):
        self.data['hechos'][0].update(clasificacion='inferido', hechos_base=['H1'], regla_inferencia='X')
        self.assertIn('INFERENCIA_CIRCULAR', self.codes())

    def test_12_indirect_inference_cycle(self):
        self.data['hechos'][0].update(clasificacion='inferido', hechos_base=['H2'], regla_inferencia='X')
        second = copy.deepcopy(self.data['hechos'][0]); second.update(id='H2', hechos_base=['H1'])
        self.data['hechos'].append(second); self.data['alcance']['hechos'].append('H2')
        self.assertIn('INFERENCIA_CIRCULAR', self.codes())

    def test_13_pending_normative_version(self):
        self.data['normas'][0]['control_temporal'] = 'pendiente'
        self.assertIn('NORMA_TEMPORAL', self.codes())

    def test_14_metadata_conflict_despite_global_confirmed(self):
        self.data['citas'][0]['datos']['ponente']['estado'] = 'discrepante'
        self.assertIn('METADATO', self.codes())

    def test_15_identity_without_ratio(self):
        self.data['citas'][0]['ratio_estado'] = 'pendiente'
        self.assertIn('RATIO_APLICABILIDAD', self.codes())

    def test_16_dissent_as_majority(self):
        self.data['citas'][0]['solo_en_salvamento'] = True
        self.assertIn('ATRIBUCION', self.codes())

    def test_17_party_argument_as_majority(self):
        self.data['citas'][0]['seccion'] = 'alegatos_parte'
        self.assertIn('ATRIBUCION', self.codes())

    def test_18_llm_origin_is_not_source(self):
        self.data['citas'][0]['origen'] = 'llm'
        self.assertIn('ORIGEN_CITA', self.codes())

    def test_19_secondary_origin_is_not_official(self):
        self.data['citas'][0]['origen'] = 'secundaria'
        self.assertIn('ORIGEN_CITA', self.codes())

    def test_20_no_update_record(self):
        self.data['citas'][0]['actualizacion'] = {}
        self.assertIn('ACTUALIZACION', self.codes())

    def test_21_unanswered_argument(self):
        self.data['argumentos'][0]['estado'] = 'pendiente'
        self.assertIn('ARGUMENTO_PENDIENTE', self.codes())

    def test_22_absorption_in_itself(self):
        self.data['argumentos'][0].update(estado='absorbido', absorbido_por='A1')
        self.assertIn('ABSORCION', self.codes())

    def test_23_decision_not_reciprocal(self):
        self.data['problemas'][0]['determinaciones'] = []
        self.assertIn('CONGRUENCIA_ENLACE', self.codes())

    def test_24_order_without_recipient_and_deadline(self):
        self.data['determinaciones'][0]['tipo'] = 'orden'
        codes = self.codes(); self.assertIn('ORDEN_PLAZO', codes); self.assertIn('CAMPO_VACIO', codes)

    def test_25_unfinished_section(self):
        self.data['apartados'][0]['estado'] = 'pendiente'
        self.assertIn('APARTADO_PENDIENTE', self.codes())

    def test_26_literal_changed(self):
        self.assertIn('INTEGRIDAD_LITERAL', self.codes(FINAL.replace('protegido', 'modificado')))

    def test_27_protection_not_in_original(self):
        self.assertIn('PROTECCION_ORIGEN', self.codes(original='Otro texto'))

    def test_28_no_original_for_protections(self):
        self.assertIn('ORIGINAL_FALTANTE', self.codes(original=None))

    def test_29_pending_marker(self):
        self.assertIn('MARCADOR_PENDIENTE', self.codes(FINAL + ' [VERIFICAR: cita]'))

    def test_30_open_substantive_finding(self):
        self.data['hallazgos'] = [{'severidad': 'sustancial', 'estado': 'pendiente'}]
        self.assertIn('HALLAZGO_ABIERTO', self.codes())

    def test_31_claimed_edit_without_actual_write(self):
        self.data['entrega']['edicion_afirmada'] = True
        self.assertIn('ESCRITURA', self.codes())

    def test_32_changed_final_version(self):
        self.data['entrega']['sha256_texto_final'] = '0' * 64
        self.assertIn('VERSION_TEXTO', self.codes())

    def test_33_no_final_text(self):
        self.assertIn('TEXTO_FINAL', self.codes(final=None))

    def test_34_empty_gate_evidence(self):
        self.data['puertas']['G3']['evidencia'] = ''
        self.assertIn('PUERTA_ABIERTA', self.codes())

    def test_35_broken_fact_reference(self):
        self.data['problemas'][0]['hechos'] = ['H9']
        self.assertIn('REFERENCIA_ROTA', self.codes())

    def test_36_silent_substantive_correction(self):
        self.data['cambios_verificados'] = [{'original': 'protegido', 'corregido': 'protegido',
                'fuente': 'fuente sintetica', 'localizador': 'p.1', 'razon': 'prueba', 'reportado': False}]
        self.assertIn('CAMBIO_NO_REPORTADO', self.codes())

    def test_37_future_date(self):
        self.data['fecha_control'] = '2999-01-01'
        self.assertIn('FECHA', self.codes())

    def test_38_cli_valid(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)
            (p/'control.json').write_text(json.dumps(self.data), encoding='utf-8')
            (p/'final.txt').write_text(FINAL, encoding='utf-8')
            cmd = [sys.executable, str(ROOT/'scripts/auditar_entrega.py'), str(p/'control.json'),
                   '--texto-final', str(p/'final.txt'), '--texto-original', str(p/'final.txt'),
                   '--reporte', str(p/'report.json')]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads((p/'report.json').read_text())['numero_bloqueos'], 0)

    def test_39_cli_does_not_overwrite_input(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'control.json'; original = json.dumps(self.data); p.write_text(original)
            r = subprocess.run([sys.executable, str(ROOT/'scripts/auditar_entrega.py'), str(p),
                                '--reporte', str(p)], capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(p.read_text(), original)

    def test_40_cli_invalid_json(self):
        with tempfile.TemporaryDirectory() as folder:
            p = Path(folder)/'bad.json'; p.write_text('{')
            r = subprocess.run([sys.executable, str(ROOT/'scripts/auditar_entrega.py'), str(p)],
                               capture_output=True, text=True, timeout=10)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stderr)['estado'], 'ENTRADA_INVALIDA')



    def test_41_essential_metadata_cannot_be_not_applicable(self):
        for field in ('corporacion', 'identificador', 'fecha'):
            with self.subTest(field=field):
                self.data = fixture()
                self.data['citas'][0]['datos'][field].update(
                    estado='no_aplica', justificacion='Excusa sintetica invalida.')
                self.assertIn('METADATO_ESENCIAL', self.codes())

    def test_42_justified_optional_metadata(self):
        self.data['citas'][0]['datos']['sala'].update(
            estado='no_aplica', justificacion='No aplica segun fuente sintetica.')
        self.assertNotIn('METADATO_ESENCIAL', self.codes())
        self.assertNotIn('METADATO', self.codes())

    def test_43_indirect_absorption_cycle(self):
        self.data['argumentos'][0].update(estado='absorbido', absorbido_por='A2')
        second = copy.deepcopy(self.data['argumentos'][0])
        second.update(id='A2', absorbido_por='A1')
        self.data['argumentos'].append(second)
        self.data['alcance']['argumentos'].append('A2')
        self.assertIn('ABSORCION_CIRCULAR', self.codes())

    def test_44_absorption_reaches_answer(self):
        second = copy.deepcopy(self.data['argumentos'][0])
        second.update(id='A2', estado='respondido')
        self.data['argumentos'].append(second)
        self.data['alcance']['argumentos'].append('A2')
        self.data['argumentos'][0].update(estado='absorbido', absorbido_por='A2')
        self.assertNotIn('ABSORCION_CIRCULAR', self.codes())

if __name__ == '__main__':
    unittest.main()
