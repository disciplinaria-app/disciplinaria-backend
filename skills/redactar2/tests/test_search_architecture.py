from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / 'SKILL.md').read_text(encoding='utf-8')
SEARCH = (ROOT / 'references' / 'busqueda-jurisprudencial-oficial.md').read_text(encoding='utf-8')
TOOLS = (ROOT / 'references' / 'herramientas-externas.md').read_text(encoding='utf-8')

class SearchArchitectureTests(unittest.TestCase):
    def test_skill_loads_search_module(self):
        self.assertIn('busqueda-jurisprudencial-oficial.md', SKILL)

    def test_multichannel_escalation_is_required(self):
        for term in ('HTTP', 'Playwright', 'Hyperresearch', 'fuente oficial'):
            self.assertIn(term, SEARCH + SKILL)

    def test_four_courts_are_covered(self):
        for term in ('Corte Constitucional', 'Corte Suprema de Justicia', 'Consejo de Estado', 'Comisión Nacional de Disciplina Judicial'):
            self.assertIn(term, SEARCH)

    def test_external_tools_are_search_multipliers(self):
        for term in ('lackeyjb/playwright-skill', 'jordan-gibbs/hyperresearch', 'vercel-labs/skills'):
            self.assertIn(term, TOOLS)

    def test_secondary_discovery_cannot_verify(self):
        self.assertIn('debe regresar al portal oficial', TOOLS)
        self.assertIn('verificación final en texto oficial', SEARCH)

    def test_word_does_not_assume_local_playwright_skill(self):
        self.assertIn('no depender de que esa skill local exista', TOOLS)

    def test_hyperresearch_patterns_are_operationalized(self):
        for term in ('búsqueda adversa', 'gap-fill', 'seguimiento de citas'):
            self.assertIn(term, TOOLS + SEARCH)

if __name__ == '__main__':
    unittest.main()
