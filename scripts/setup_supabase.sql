-- ═══════════════════════════════════════════════════════════════════════════
-- DISCIPLINAR[IA] — Configuración de Supabase
-- Ejecutar UNA sola vez en el Editor SQL de Supabase
-- ═══════════════════════════════════════════════════════════════════════════

-- 1. Habilitar extensión pgvector (si no está habilitada)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Tabla de artículos legales con embeddings
CREATE TABLE IF NOT EXISTS articulos_legales (
    id               BIGSERIAL PRIMARY KEY,
    ley              TEXT NOT NULL,          -- '1123' | '1952'
    numero_articulo  TEXT NOT NULL,
    titulo           TEXT DEFAULT '',
    contenido        TEXT NOT NULL,
    embedding        VECTOR(1536),
    created_at       TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (ley, numero_articulo)
);

-- 3. Índice vectorial para búsqueda semántica eficiente (coseno)
CREATE INDEX IF NOT EXISTS articulos_legales_embedding_idx
    ON articulos_legales
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- 4. Función RPC para búsqueda vectorial por similitud coseno
CREATE OR REPLACE FUNCTION match_articulos(
    query_embedding  VECTOR(1536),
    match_ley        TEXT,
    match_count      INT   DEFAULT 5,
    match_threshold  FLOAT DEFAULT 0.75
)
RETURNS TABLE (
    numero_articulo TEXT,
    titulo          TEXT,
    contenido       TEXT,
    similitud       FLOAT
)
LANGUAGE SQL STABLE AS $$
    SELECT
        numero_articulo,
        titulo,
        contenido,
        1 - (embedding <=> query_embedding) AS similitud
    FROM   articulos_legales
    WHERE  ley = match_ley
      AND  1 - (embedding <=> query_embedding) > match_threshold
    ORDER  BY embedding <=> query_embedding
    LIMIT  match_count;
$$;

-- 5. RLS: la tabla es de solo lectura para anon; escritura solo service_role
ALTER TABLE articulos_legales ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Lectura publica de articulos" ON articulos_legales
    FOR SELECT USING (true);

-- ═══════════════════════════════════════════════════════════════════════════
-- Verificación: debería mostrar 0 filas (tabla vacía antes de cargar_leyes)
SELECT COUNT(*) AS articulos_cargados FROM articulos_legales;
-- ═══════════════════════════════════════════════════════════════════════════
