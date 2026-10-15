# redactar2-mcp · Verificador jurisprudencial oficial

Servidor MCP que sale a los portales oficiales de la Corte Constitucional, la Corte Suprema de Justicia, el Consejo de Estado y la Comisión Nacional de Disciplina Judicial, trae el documento oficial y lo compara con la cita que usted quiere usar. **No redacta ni decide si una sentencia respalda su tesis**: devuelve evidencia (URL abierta, hash, campo por campo, pasaje y su sección) para que la skill `redactar2` o `redaccion-consideraciones` razone con eso a la vista.

## Qué hace, en una frase por herramienta

| Herramienta | Para qué |
|---|---|
| `verificar_cita` | Dada una cita (corporación + número o radicado, y opcionalmente ponente, fecha, sala y la subregla que usted invoca), abre el documento oficial y dice campo por campo si coincide. Si envía la subregla, localiza el pasaje más parecido y avisa si está en un salvamento de voto o en los antecedentes. |
| `buscar_providencia` | Dada una subregla abstracta, consulta el buscador oficial con varias formulaciones (frase exacta, términos, sinónimos, búsqueda adversa, años) y devuelve candidatos **sin verificar**. |
| `leer_providencia` | Entrega el texto oficial por partes, con el número de párrafo/página y la sección estimada (consideraciones, resolutiva, salvamento…). |
| `actualizar_linea` | Busca decisiones de los cuatro años anteriores a una fecha de corte sobre una subregla, a partir de una sentencia hito, y marca señales de rectificación. |
| `estado_verificacion` | Consulta un trabajo largo. |
| `diagnosticar_portales` | Dice qué portales responden hoy y si el navegador automatizado está activo. Úsela primero cuando algo falle. |

## Reglas que el servidor hace cumplir

- Solo consulta dominios oficiales (`.gov.co` de las cortes y de la Rama Judicial). Cualquier otra URL se rechaza con estado `bloqueada`.
- Rechaza consultas con cédulas, radicados de proceso, calidad procesal seguida de nombre propio, datos de salud o párrafos enteros: el expediente nunca sale del despacho.
- Una solicitud por segundo por portal, con `User-Agent` identificable.
- Distingue `sin_resultados`, `no_hallada`, `discrepante`, `parcial`, `portal_no_disponible`, `timeout` y `bloqueada`. Ninguno de los cuatro últimos significa que la providencia no exista.
- Nunca completa un dato por inferencia. Si el ponente no aparece en el documento, el campo queda `no_hallado`.

## Publicar en Google Cloud Run (guía sin tecnicismos)

Cloud Run es un servicio de Google que ejecuta el programa solo cuando alguien lo llama y cobra por segundos de uso. Con el nivel gratuito y los créditos de Google AI Pro, el costo esperado para un despacho es cero o centavos.

### Una sola vez

1. **Cree el proyecto.** Entre a <https://console.cloud.google.com>, cree un proyecto (por ejemplo `redactar2-mcp`) y active la facturación (necesaria aunque no se cobre nada). Anote el **ID del proyecto**.
2. **Active los servicios.** En el buscador de la consola escriba *Cloud Run* y pulse *Habilitar*; repita con *Cloud Build* y *Artifact Registry*.
3. **Instale la herramienta de línea de comandos** `gcloud` en su computador: <https://cloud.google.com/sdk/docs/install>. Luego, en una terminal:
   ```bash
   gcloud auth login
   gcloud config set project ID-DE-SU-PROYECTO
   ```
4. **Genere la llave** que Claude usará para hablar con el servidor (una contraseña larga):
   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Guárdela: la necesitará en el paso 6 y al conectar Claude.

### Publicar (y volver a publicar tras cada cambio)

5. Desde la carpeta `mcp/` de este repositorio:
   ```bash
   gcloud run deploy redactar2-mcp \
     --source . \
     --region us-east1 \
     --memory 2Gi --cpu 1 --timeout 120 \
     --min-instances 0 --max-instances 2 \
     --allow-unauthenticated \
     --set-env-vars MCP_API_KEY=PEGUE-AQUI-SU-LLAVE,MCP_CONTACTO=su-correo@ejemplo.com
   ```
   `--allow-unauthenticated` deja que Claude llegue a la puerta; la llave (`MCP_API_KEY`) es la que abre. Sin llave correcta el servidor responde 401.
   La primera publicación tarda de 5 a 10 minutos porque construye la imagen con el navegador. Use la URL con el número de proyecto, `https://redactar2-mcp-<número>.<región>.run.app` (la imprime `publicar.sh`); la forma antigua `*-<hash>-ue.a.run.app` devolvió 404 del frente de Google para las peticiones POST.
6. Compruebe: abra `https://SU-URL/health` en el navegador. Debe ver `{"estado":"ok",...}`.

### Conectar a Claude

7. En claude.ai → *Configuración* → *Conectores* → *Añadir conector personalizado*:
   - Nombre: `Verificador jurisprudencial`
   - URL: la que imprime `publicar.sh` con la llave dentro: `https://SU-URL/k/SU-LLAVE/mcp`
   - Sin autenticación adicional (claude.ai no envía cabeceras propias a conectores personalizados; por eso la llave viaja en la ruta, siempre bajo HTTPS). Si el asistente de claude.ai dice «No se ha podido comprobar el servidor», pulse *Continuar de todas formas*.
   - Clientes que sí admiten cabeceras (Claude Code, Cursor, etc.) pueden usar `https://SU-URL/mcp` con `Authorization: Bearer SU-LLAVE`.
8. En una conversación nueva, pida: «Ejecuta `diagnosticar_portales`». Si los cuatro portales responden `ok`, está listo. Si alguno dice `portal_no_disponible` o `timeout`, es el portal, no el servidor: reintente más tarde.

### Primera prueba real

Pida a Claude: «Verifica con el conector la sentencia SU-107 de 2024 de la Corte Constitucional» y luego «lee el segmento 0». Compare con lo que ve usted en la relatoría. Después pruebe una de la CNDJ: esa pasa por el navegador automatizado y es la que más puede necesitar ajuste de selectores (ver `docs/portales.md`).

## Variables de entorno

Ver `.env.example`. Las URLs y selectores de cada portal se pueden cambiar sin tocar código (`CC_BASE`, `CNDJ_RELATORIA`, `WR_CAMPO_TEXTO`, etc.), lo que permite reaccionar a un rediseño del portal con un redespliegue de un minuto.

## Ejecutar y probar en su computador

```bash
cd mcp
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium            # solo para pruebas locales con navegador
python -m unittest discover -s tests   # 18 pruebas con sentencias sintéticas, sin internet
MCP_API_KEY=prueba python server.py    # http://localhost:8080/health
```

## Estado de esta versión (0.1.0)

- Probado sin internet con documentos sintéticos: comparación de campos, roles de sección, pasaje en salvamento, privacidad, corpus y estados técnicos.
- **No probado todavía contra los portales reales**: el entorno donde se construyó no alcanza dominios `.gov.co`. Las rutas y selectores son el punto de partida documentado; `diagnosticar_portales` y la primera prueba real dirán qué hay que ajustar. El adaptador de la Corte Constitucional usa el patrón histórico de URL de la relatoría; los de CSJ, Consejo de Estado y CNDJ dependen del navegador y de selectores configurables.
- Sin base de datos: el corpus vive en `/tmp` del contenedor y se pierde al apagarse; es suficiente para la caché de 30 días dentro de una sesión de trabajo. Si más adelante quiere persistencia, se añade un bucket de Cloud Storage.
- Sin OAuth: autenticación por llave (en cabecera o en la ruta `/k/<llave>/mcp`), adecuada para un solo despacho. Si la llave se filtra, basta redesplegar con `MCP_API_KEY=nueva ./publicar.sh …` para rotarla.
