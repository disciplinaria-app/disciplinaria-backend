#!/usr/bin/env bash
# Publica redactar2-mcp en Google Cloud Run. Uso:
#   ./publicar.sh ID-DEL-PROYECTO su-correo@ejemplo.com
# La primera vez tarda 5-10 minutos. Imprime al final la URL y la llave.
set -euo pipefail
PROYECTO="${1:?Falta el ID del proyecto de Google Cloud}"
CONTACTO="${2:?Falta un correo de contacto para el User-Agent}"
REGION="${REGION:-us-east1}"
# Reutilizar la llave del servicio ya publicado, si existe; si no, generar una.
LLAVE="${MCP_API_KEY:-}"
if [ -z "$LLAVE" ]; then
  LLAVE="$(gcloud run services describe redactar2-mcp --region "$REGION" --project "$PROYECTO" --format json 2>/dev/null \
    | python3 -c 'import sys,json
try:
  d=json.load(sys.stdin)
  for e in d["spec"]["template"]["spec"]["containers"][0].get("env",[]):
    if e.get("name")=="MCP_API_KEY" and e.get("value"): print(e["value"]); break
except Exception: pass' 2>/dev/null || true)"
fi
if [ -z "$LLAVE" ]; then
  LLAVE="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
fi

gcloud config set project "$PROYECTO" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com >/dev/null

gcloud run deploy redactar2-mcp \
  --source "$(dirname "$0")" \
  --region "$REGION" \
  --memory 2Gi --cpu 1 --timeout 120 \
  --min-instances 0 --max-instances 2 \
  --allow-unauthenticated \
  --set-env-vars "MCP_API_KEY=${LLAVE},MCP_CONTACTO=${CONTACTO}"

# Usar la URL determinista (con el número de proyecto): la forma antigua
# (*-<hash>-<región>.a.run.app) ha mostrado 404 del frente de Google para POST.
NUMERO="$(gcloud projects describe "$PROYECTO" --format 'value(projectNumber)')"
URL="https://redactar2-mcp-${NUMERO}.${REGION}.run.app"
echo
echo "=============================================================="
echo "Listo. Conecte en claude.ai → Conectores → Añadir conector personalizado:"
echo "  URL del conector (lleva la llave dentro; no necesita autenticación aparte):"
echo "  ${URL}/k/${LLAVE}/mcp"
echo
echo "Para clientes que admiten cabeceras (Claude Code, etc.):"
echo "  URL:    ${URL}/mcp"
echo "  Llave:  ${LLAVE}   (Authorization: Bearer)"
echo "Comprobación: curl ${URL}/health"
echo "Guarde la URL completa: contiene la llave."
echo "=============================================================="
