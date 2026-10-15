#!/usr/bin/env bash
# Ejecuta búsquedas reales en los portales a través del servidor MCP y muestra
# cómo se presentan los resultados. Uso: ./inspeccionar-busqueda.sh 'https://<servicio>/k/<llave>/mcp'
set -euo pipefail
MCP="${1:?Falta la URL del conector (con la llave)}"
llamar() {
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
print("   texto:", (d.get("texto_inicio") or "")[:1500])
print("   TABLAS:")
for t in d.get("tablas",[]):
    if t.get("filas",0) < 2: continue
    print("     id=",t.get("id"),"filas=",t.get("filas"))
    for m in t.get("muestra",[]): print("        |", m)
    for e in t.get("enlaces_fila",[]): print("        a:", e.get("texto"), "->", e.get("href"), "id=", e.get("id"))
print("   LISTAS/TARJETAS:")
for l in d.get("listas",[])[:4]:
    print("     ", l.get("tag"), "id=", l.get("id"), "clase=", l.get("clase"))
    print("        ", l.get("texto")[:300])
    for e in l.get("enlaces",[]): print("        a:", e.get("texto"), "->", e.get("href"))
print("   ENLACES:")
for e in d.get("enlaces",[])[:25]: print("     ", e.get("texto")[:60], "->", e.get("href"))
print()
'
}
echo "### A. Corte Constitucional — frase corta por URL"
llamar "https://www.corteconstitucional.gov.co/relatoria/buscador-jurisprudencia/texto/2022-01-01/2026-10-15/plazo%20razonable/0/0" '[{"tipo":"esperar","ms":9000}]' 'relatoria/20|\.htm|\.pdf' 6000
echo "### B. CNDJ — texto completo"
llamar "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml" \
  '[{"tipo":"fill","selector":"xpath=//*[normalize-space(text())=\"Texto Completo\"]/following::input[1]","valor":"ilicitud sustancial"},{"tipo":"click","selector":"button[id^=\"searchForm\"]:has-text(\"Buscar\"):visible"},{"tipo":"esperar","ms":12000}]' \
  'pdf|Documento|descarg|xhtml' 6000
echo "### C. Consejo de Estado — WebRelatoria tradicional (campos)"
llamar "https://servicios.consejodeestado.gov.co/WebRelatoria/ce/index.xhtml" '[]' 'pdf|Documento' 6000
echo "### D. CNDJ — texto completo, espera larga y HTML de la tabla de resultados"
llamar_html() {
  local args
  args=$(python3 -c 'import json,sys; print(json.dumps({"url":sys.argv[1],"acciones":json.loads(sys.argv[2]),"esperar_ms":int(sys.argv[3]),"selector_html":sys.argv[4]}))' "$1" "$2" "$3" "$4")
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
print("== URL final:", d.get("url_final"), "| estado", d.get("estado"), d.get("detalle",""), "| errores:", d.get("errores_acciones"))
print("   texto:", (d.get("texto_inicio") or "")[:600])
print("   TABLAS (todas):")
for t in d.get("tablas",[]):
    print("     id=",t.get("id"),"filas=",t.get("filas"))
    for m in t.get("muestra",[]): print("        |", m)
    for e in t.get("enlaces_fila",[]): print("        a:", e.get("texto"), "->", e.get("href"), "id=", e.get("id"))
print("   HTML_SELECTOR:")
print(d.get("html_selector"))
print()
'
}
for variante in \
  'texto-completo|[{"tipo":"click_texto","texto":"Sentencia"},{"tipo":"fill","selector":"xpath=//*[normalize-space(text())=\"Texto Completo\"]/following::input[1]","valor":"ilicitud sustancial"}]' \
  'tema|[{"tipo":"click_texto","texto":"Sentencia"},{"tipo":"fill","selector":"input[id$=\":temaInput\"]","valor":"ilicitud sustancial"}]' \
  'tema-comillas|[{"tipo":"click_texto","texto":"Sentencia"},{"tipo":"fill","selector":"input[id$=\":temaInput\"]","valor":"\"ilicitud sustancial\""}]' \
  'ponente-vacio-solo-sentencia|[{"tipo":"click_texto","texto":"Sentencia"}]' ; do
  nombre="${variante%%|*}"; acciones="${variante#*|}"
  acciones="${acciones%]}"',{"tipo":"click","selector":"button[id^=\"searchForm\"]:has-text(\"Buscar\"):visible"},{"tipo":"esperar","ms":20000}]'
  echo "--- variante: $nombre"
  llamar_html "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml" "$acciones" 4000 "[id='resultForm:jurisTable']"
done
