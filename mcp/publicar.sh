#!/usr/bin/env bash
# Publica redactar2-mcp en Google Cloud Run. Uso:
#   ./publicar.sh ID-DEL-PROYECTO su-correo@ejemplo.com
# La primera vez tarda 5-10 minutos. Imprime al final la URL y la llave.
set -euo pipefail
PROYECTO="${1:?Falta el ID del proyecto de Google Cloud}"
CONTACTO="${2:?Falta un correo de contacto para el User-Agent}"
REGION="${REGION:-us-east1}"
LLAVE="${MCP_API_KEY:-$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')}"

gcloud config set project "$PROYECTO" >/dev/null
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com >/dev/null

gcloud run deploy redactar2-mcp \
  --source "$(dirname "$0")" \
  --region "$REGION" \
  --memory 2Gi --cpu 1 --timeout 120 \
  --min-instances 0 --max-instances 2 \
  --allow-unauthenticated \
  --set-env-vars "MCP_API_KEY=${LLAVE},MCP_CONTACTO=${CONTACTO}"

URL="$(gcloud run services describe redactar2-mcp --region "$REGION" --format 'value(status.url)')"
echo
echo "=============================================================="
echo "Listo. Conecte en claude.ai → Conectores → Añadir conector:"
echo "  URL:    ${URL}/mcp"
echo "  Llave:  ${LLAVE}"
echo "Comprobación: curl ${URL}/health"
echo "Guarde la llave: no vuelve a mostrarse."
echo "=============================================================="
