#!/usr/bin/env bash
# Ejecuta una búsqueda real en cada portal a través del servidor MCP y muestra
# cómo se presentan los resultados (tablas, listas, enlaces). Uso:
#   ./inspeccionar-busqueda.sh 'https://<servicio>/k/<llave>/mcp'
set -euo pipefail
MCP="${1:?Falta la URL del conector (con la llave)}"

llamar() {  # $1=url $2=acciones(json) $3=patron $4=esperar_ms
  local args
  args=$(python3 -c 'import json,sys; print(json.dumps({"url":sys.argv[1],"acciones":json.loads(sys.argv[2]),"patron_enlaces":(sys.argv[3] or None),"esperar_ms":int(sys.argv[4])}))' "$1" "$2" "$3" "$4")
  curl -s -X POST "$MCP" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"inspeccionar_pagina\",\"arguments\":$args}}" \
  | python3 -c '
import json,sys
r=json.load(sys.stdin); res=r.get("result",{}); d=res.get("structuredContent") or {}
if not d:
    for c in res.get("content",[]):
        if c.get("type")=="text":
            try: d=json.loads(c["text"]); break
            except Exception: pass
if not d: print("RESPUESTA:", json.dumps(r)[:1500]); sys.exit()
print("== URL final:", d.get("url_final"), "| estado", d.get("estado"), d.get("detalle",""))
print("   errores_acciones:", d.get("errores_acciones"))
print("   caracteres:", d.get("caracteres_texto"))
print("   texto:", (d.get("texto_inicio") or "")[:1500])
print("   TABLAS:")
for t in d.get("tablas",[]):
    print("     id=",t.get("id"),"filas=",t.get("filas"))
    for m in t.get("muestra",[]): print("        |", m)
    for e in t.get("enlaces_fila",[]): print("        a:", e.get("texto"), "->", e.get("href"), "id=", e.get("id"))
print("   LISTAS/TARJETAS:")
for l in d.get("listas",[]):
    print("     ", l.get("tag"), "id=", l.get("id"), "clase=", l.get("clase"))
    print("        ", l.get("texto"))
    for e in l.get("enlaces",[]): print("        a:", e.get("texto"), "->", e.get("href"))
print("   ENLACES:")
for e in d.get("enlaces",[])[:30]: print("     ", e.get("texto")[:60], "->", e.get("href"))
print()
'
}

echo "### A. Corte Constitucional — búsqueda por texto completo"
llamar "https://www.corteconstitucional.gov.co/relatoria/buscador-jurisprudencia" \
  '[{"tipo":"select","selector":"#selectBuscador","valor":"Texto completo de las providencias"},{"tipo":"fill","selector":"#textoBuscador","valor":"mora administrativa plazo razonable"},{"tipo":"click","selector":"button:has-text(\"Buscar\")"},{"tipo":"esperar","ms":9000}]' \
  'relatoria|\.htm|\.pdf|sentencia' 6000

echo "### B. CNDJ — búsqueda por tema"
llamar "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml" \
  '[{"tipo":"click_texto","texto":"Criterios de búsqueda"},{"tipo":"esperar","ms":1000},{"tipo":"fill","selector":"input[id$=\":temaInput\"]","valor":"ilicitud sustancial"},{"tipo":"click","selector":"button[id^=\"searchForm\"]:has-text(\"Buscar\"):visible"},{"tipo":"esperar","ms":9000}]' \
  'pdf|Documento|descarg' 6000

echo "### C. Consejo de Estado — buscador de providencias tituladas (sin acciones)"
llamar "https://samai.consejodeestado.gov.co/TitulacionRelatoria/BuscadorProvidenciasTituladas.aspx" '[]' 'pdf|Providencia|Documento' 6000
