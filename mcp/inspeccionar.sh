#!/usr/bin/env bash
# Inspecciona los portales oficiales a través del servidor MCP ya publicado y
# resume campos, botones y enlaces. Uso:
#   ./inspeccionar.sh 'https://<servicio>/k/<llave>/mcp'  [url_opcional] [patron_opcional]
set -euo pipefail
MCP="${1:?Falta la URL del conector (con la llave)}"
URL_UNICA="${2:-}"
PATRON_UNICO="${3:-}"

llamar() {  # $1=url $2=patron $3=esperar_ms
  local args
  args=$(python3 -c 'import json,sys; print(json.dumps({"url":sys.argv[1],"esperar_ms":int(sys.argv[3]),"patron_enlaces":(sys.argv[2] or None)}))' "$1" "$2" "$3")
  curl -s -X POST "$MCP" -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream' \
    -d "{\"jsonrpc\":\"2.0\",\"id\":1,\"method\":\"tools/call\",\"params\":{\"name\":\"inspeccionar_pagina\",\"arguments\":$args}}" \
  | python3 -c '
import json,sys
r=json.load(sys.stdin)
res=r.get("result",{})
d=res.get("structuredContent") or {}
if not d:
    for c in res.get("content",[]):
        if c.get("type")=="text":
            try: d=json.loads(c["text"]); break
            except Exception: pass
if not d: print("RESPUESTA:", json.dumps(r)[:1500]); sys.exit()
print("== URL final:", d.get("url_final"), "| HTTP", d.get("codigo_http"), "| estado", d.get("estado"), d.get("detalle",""))
print("   título:", d.get("titulo"), "| caracteres:", d.get("caracteres_texto"))
print("   inicio:", (d.get("texto_inicio") or "")[:300])
print("   iframes:", d.get("iframes"))
print("   CAMPOS:")
for c in d.get("campos",[]):
    if c.get("type") in ("hidden",): continue
    print("     ", c.get("tag"), "id=",c.get("id"), "name=",c.get("name"), "type=",c.get("type"), "label=",c.get("etiqueta"), "vis=",c.get("visible"), ("opc="+"|".join(c["opciones"][:12])) if c.get("opciones") else "")
print("   BOTONES:")
for b in d.get("botones",[]):
    if b.get("texto") or b.get("id"): print("     ", b.get("tag"), "id=",b.get("id"), "texto=",b.get("texto"), "vis=",b.get("visible"))
print("   ENLACES:")
for e in d.get("enlaces",[])[:40]: print("     ", e.get("texto")[:50], "->", e.get("href"))
print()
'
}

if [ -n "$URL_UNICA" ]; then
  llamar "$URL_UNICA" "$PATRON_UNICO" 8000; exit
fi
echo "### 1. Corte Constitucional — sentencia por patrón histórico"
llamar "https://www.corteconstitucional.gov.co/relatoria/2024/SU-107-24.htm" 'SU-?107|\.htm|\.pdf|buscador' 8000
echo "### 2. Corte Constitucional — relatoría"
llamar "https://www.corteconstitucional.gov.co/relatoria/" 'buscador|jurisprudencia|relatoria' 8000
echo "### 3. CNDJ — formulario"
llamar "https://jurisprudencia.ramajudicial.gov.co/WebRelatoria/cndj/index.xhtml" '' 6000
echo "### 4. Consejo de Estado — SAMAI"
llamar "https://samai.consejodeestado.gov.co" 'jurisprudencia|biblioteca|unificaci' 6000
