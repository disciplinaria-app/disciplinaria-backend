# Registro de trazabilidad y auditor local

## 1. Finalidad y límite

Crear el registro durante el trabajo, no al final para justificar retrospectivamente una respuesta. Su finalidad es enlazar piezas, hechos, normas, citas, argumentos, problemas y determinaciones. El registro contiene conclusiones de trabajo y evidencia localizada, no razonamiento privado.

El auditor `scripts/auditar_entrega.py` es **local, determinista y sin acceso a internet**. Examina consistencia de las declaraciones suministradas y cadenas literales protegidas. No comprueba autenticidad de un documento, si una URL existe, si es realmente oficial, verdad de un hecho, validez del derecho, ratio, pertinencia o calidad de una argumentación. Tampoco descubre automáticamente argumentos omitidos del propio inventario. Una declaración falsa puede superar un control estructural; por eso las fases de lectura y contraste no se sustituyen con el script.

## 2. Crear el control

Copiar `assets/control-entrega.json` a un archivo del caso, sin modificar la plantilla de la skill. Completar `caso_id` con un identificador local, `fecha_control` en formato ISO y `modo` (`integral`, `delimitado`, `editorial` o `auditoria`). No usar el nombre de una parte cuando baste un identificador local. Poner `cierre_solicitado: true` solo al comprobar la entrega.

`revision_cobertura` exige `comprobada: true` y `evidencia` que identifique la revisión del inventario contra el material disponible. No significa que el universo del expediente haya sido conocido. En `alcance`, listar los identificadores esperados por cada uno de los ocho grupos; toda fila debe figurar en ese inventario y viceversa. Mantener los identificadores únicos en el conjunto.

En revisiones delimitadas o editoriales, dejar vacíos los grupos que no correspondan y justificar controles no aplicables. No fabricar hechos, normas ni providencias para completar la plantilla. El cierre integral exige al menos piezas, problemas, apartados y determinaciones.

## 3. Campos de las ocho colecciones

### Piezas

`id`, `localizador`, `esencial` (booleano), `estado_lectura` (`completa`, `parcial`, `no_accesible` o `no_aportada`) y `segmentos_pendientes` (lista). Una pieza esencial sin lectura completa exige bloqueo, salvo que su ausencia tenga un tratamiento jurídico resoluble realmente verificado: en tal caso, `faltante_resoluble: true` y `fundamento_faltante` localizable. No usar esa excepción para disfrazar falta de lectura.

### Hechos

`id`, `enunciado`, `clasificacion` (`alegado`, `acreditado`, `controvertido`, `inferido`, `no_acreditado`), `valoracion`, `piezas` (ids), `premisa_decisiva` (booleano) y, cuando sea decisivo, `localizador_fuente`. Para inferencias añadir `hechos_base` (ids) y `regla_inferencia`. No crear ciclos de fundamentación. Una falta de acreditación relevante se documenta por su revisión y sus consecuencias, no inventando una prueba de inexistencia.

### Normas

`id`, `identificacion`, `version_aplicable`, `control_temporal: verificado`, `url_oficial`, `consultada_en` (fecha ISO), `localizador` y `aplicacion_caso`. Registrar las normas utilizadas en la versión final; conservar candidatos descartados en un registro separado de investigación.

### Citas

`id`, `estado_identidad: confirmada`, `origen: fuente_oficial`, `url_oficial`, `consultada_en`, `pasaje`, `localizador`, `justificacion_aplicabilidad`, `uso` (`fundamento` o `contraste_identificado`), `seccion`, `solo_en_salvamento` (booleano), `ratio_estado: verificada`, `aplicabilidad: verificada` y `actualizacion` con `estado: realizada` y `evidencia` de la búsqueda.

En `datos`, incluir `corporacion`, `sala`, `ponente`, `identificador` y `fecha`. Cada uno contiene `estado`, `valor`, `evidencia` y `localizador`. Si un campo realmente no aplica, usar `estado: no_aplica` con `justificacion`, evidencia y localizador; no confundirlo con no hallado. Los datos fundamentales de identidad no se omiten para salvar una comprobación fallida.

Para uso como fundamento, `seccion` debe reflejar `razones_mayoria` o `resolutiva`, sin perjuicio de la revisión semántica obligatoria. En contraste, identificar la sección real y el límite. El campo `ratio_estado` en un contraste expresa que se verificó la naturaleza de la proposición, no que un voto se convierta en ratio de la mayoría.

### Argumentos

`id`, `tesis`, `estado` (`respondido`, `absorbido` o `no_abordable_fundado`), `respuesta`, `localizador_respuesta` y `problemas` (ids). Para absorción, incluir `absorbido_por`, referido a un argumento distinto cuya respuesta cubra el punto. La motivación de no abordar debe expresar una razón jurídica, no solo una etiqueta.

### Problemas

`id`, `pregunta`, `conclusion`, `localizador`, `estado` (`resuelto` o `no_abordable_fundado`), listas `hechos`, `normas`, `citas`, `determinaciones` y booleano `requiere_decision`. Toda conclusión que requiera expresión decisoria debe vincularse a una determinación. Explicar las exclusiones fundadas.

### Determinaciones

`id`, `texto`, `fundamento_localizador`, `tipo` y `problemas` (ids). Los enlaces entre problema y determinación deben ser recíprocos. Si `tipo: orden`, añadir `destinatario`, `conducta` y `plazo` o `plazo_no_aplica` con justificación. El script solo revisa existencia de los campos, no la competencia para emitir la orden ni su ejecutabilidad real.

### Apartados

`id`, `titulo`, `estado: completo` y `localizador`. Inventariar los apartados comprendidos en el encargo; no declarar cerrada toda la providencia cuando solo se revisó un capítulo.

## 4. Protecciones, cambios y hallazgos

`protecciones`: listas de cadenas que deben conservarse, cada una con `texto` y `minimo` (número entero de apariciones). Obtenerlas del original: citas, notas y datos significativos. El cotejo es literal, sensible a cambios de texto. La extracción de DOCX/PDF debe ser consistente entre original y final; diferencias de extracción requieren examen, no alteración del documento para superar el control.

`cambios_verificados`: cada corrección sustancial contiene `original`, `corregido`, `fuente`, `localizador`, `razon` y `reportado: true`. No mantener simultáneamente como cadena intocable el fragmento cuya corrección fue justificada. No eximir datos de protección sin registrar la razón.

`hallazgos`: registrar `severidad`, `estado` y, para los resueltos, `evidencia_cierre`. Un hallazgo sustancial o bloqueante pendiente impide el cierre. Los controles no sustituyen el examen de contradicciones no reflejadas en la matriz.

`puertas`: G0 a G7, cada una con `estado` (`superada`, `no_aplica` o pendiente durante el trabajo) y `evidencia`. Justificar la no aplicación según el alcance; no declararla para eludir una fase necesaria.

`entrega`: `medio`, `referencia`, `relectura_confirmada`, `edicion_afirmada` y `escritura_confirmada`. Opcionalmente incluir `sha256_texto_final` para comprobar versión. El reporte genera el hash del texto recibido; no es un hash del archivo Word salvo que se calcule y registre aparte.

## 5. Ejecutar y leer el resultado

Requisitos: Python 3.10 o posterior; solo biblioteca estándar. Usar la herramienta de ejecución disponible en el entorno, nunca simular el resultado. No enviar el control a un servicio externo.

```bash
python scripts/auditar_entrega.py /ruta/control.json \
  --texto-original /ruta/original.txt \
  --texto-final /ruta/final.txt \
  --reporte /ruta/reporte.json
```

Los textos deben ser UTF-8. El script acepta hasta 8 MiB por entrada como límite local de seguridad, no como límite del conector. El reporte no puede sobrescribir un archivo de entrada.

Salida 0: `SIN_BLOQUEOS_ESTRUCTURALES_DETECTADOS`. Salida 1: `BLOQUEOS_ESTRUCTURALES`. Salida 2: `ENTRADA_INVALIDA`. Ninguno de estos estados certifica corrección jurídica. Una detección de marcador dentro de una cita auténtica exige revisión manual; no modificar una cita para lograr salida 0.

Si no existe entorno de ejecución, aplicar manualmente el registro y decir que no se ejecutó el control automatizado. No bloquear la producción de texto por carecer de Python; conservar los controles sustanciales.

## 6. Probar el auditor

```bash
python -m unittest discover -s tests -v
```

Los tests usan nombres, reglas y URLs deliberadamente sintéticos. No son providencias ni evidencia de un caso. Las pruebas del auditor son distintas de las pruebas de comportamiento de la skill y de la homologación del MCP con citas reales aportadas por el usuario.
