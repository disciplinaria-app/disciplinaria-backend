"""
Generación de .docx con control de cambios y comentarios al margen.

Agentes 1-3 (FORMA, ESTILO JUDICIAL, COHERENCIA NARRATIVA):
  Inserta <w:del> (rojo tachado) + <w:ins> (verde subrayado) donde se encuentre
  el texto de ubicacion. Si no se encuentra, cae a comentario.

Agentes 4-5 (FONDO ARGUMENTATIVO, NORMATIVO):
  Inserta comentario al margen con error, ubicacion y correccion.
"""

import copy
import io
import zipfile
from datetime import datetime, timezone
from lxml import etree

from docx import Document
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"

AGENTES_TRACK = {"FORMA", "ESTILO JUDICIAL", "COHERENCIA NARRATIVA"}


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── Búsqueda de texto ─────────────────────────────────────────────────────────

def _find_paragraph(doc: Document, texto: str) -> int | None:
    needle = texto.lower().strip()
    if not needle:
        return None
    for i, para in enumerate(doc.paragraphs):
        if needle in para.text.lower():
            return i
    return None


def _run_map(para_el) -> list[tuple[int, int, object, str]]:
    """Retorna [(start, end, run_el, text)] para todos los <w:r> del párrafo."""
    result, pos = [], 0
    for r in para_el.findall(f"{{{W}}}r"):
        t_el = r.find(f"{{{W}}}t")
        text = (t_el.text or "") if t_el is not None else ""
        result.append((pos, pos + len(text), r, text))
        pos += len(text)
    return result


# ── Track changes (w:del + w:ins) ────────────────────────────────────────────

def _make_rpr(orig_rpr, color: str, extra: list[str]) -> object:
    rpr = OxmlElement("w:rPr")
    if orig_rpr is not None:
        skip = {"color", "strike", "u", "rStyle"}
        for child in orig_rpr:
            if etree.QName(child).localname not in skip:
                rpr.append(copy.deepcopy(child))
    c = OxmlElement("w:color")
    c.set(qn("w:val"), color)
    rpr.append(c)
    for tag in extra:
        el = OxmlElement(tag)
        if tag == "w:u":
            el.set(qn("w:val"), "single")
        rpr.append(el)
    return rpr


def _make_t(tag: str, text: str) -> object:
    el = OxmlElement(tag)
    el.text = text
    if text and (text[0] == " " or text[-1] == " "):
        el.set(XML_SPACE, "preserve")
    return el


def insertar_track_change(doc: Document, para_idx: int, ubicacion: str,
                          correccion: str, autor: str, rev_id: int) -> bool:
    """
    Busca ubicacion en el párrafo y reemplaza con w:del + w:ins.
    Retorna True si tuvo éxito.
    """
    para_el = doc.paragraphs[para_idx]._p
    rmap = _run_map(para_el)
    if not rmap:
        return False

    combined = "".join(t for _, _, _, t in rmap)
    pos = combined.lower().find(ubicacion.lower().strip())
    if pos == -1:
        return False

    end = pos + len(ubicacion)
    texto_real = combined[pos:end]
    affected = [(s, e, r, t) for s, e, r, t in rmap if s < end and e > pos]
    if not affected:
        return False

    now = _now()
    first_r = affected[0][2]
    orig_rpr = first_r.find(f"{{{W}}}rPr")

    # <w:del>
    del_el = OxmlElement("w:del")
    del_el.set(qn("w:id"), str(rev_id))
    del_el.set(qn("w:author"), autor)
    del_el.set(qn("w:date"), now)
    del_r = OxmlElement("w:r")
    del_r.append(_make_rpr(orig_rpr, "FF0000", ["w:strike"]))
    del_r.append(_make_t("w:delText", texto_real))
    del_el.append(del_r)

    # <w:ins>
    ins_el = OxmlElement("w:ins")
    ins_el.set(qn("w:id"), str(rev_id + 1))
    ins_el.set(qn("w:author"), autor)
    ins_el.set(qn("w:date"), now)
    ins_r = OxmlElement("w:r")
    ins_r.append(_make_rpr(orig_rpr, "00B050", ["w:u"]))
    ins_r.append(_make_t("w:t", correccion))
    ins_el.append(ins_r)

    # Posición de inserción
    parent = first_r.getparent()
    insert_idx = list(parent).index(first_r)

    first_s = affected[0][0]
    last_e = affected[-1][1]
    prefix = combined[first_s:pos]
    suffix = combined[end:last_e]

    # Eliminar runs afectados
    for _, _, r_el, _ in affected:
        if r_el.getparent() is not None:
            r_el.getparent().remove(r_el)

    idx = insert_idx

    if prefix:
        pre_r = copy.deepcopy(first_r)
        t_el = pre_r.find(f"{{{W}}}t")
        if t_el is None:
            t_el = OxmlElement("w:t")
            pre_r.append(t_el)
        t_el.text = prefix
        if prefix[0] == " " or prefix[-1] == " ":
            t_el.set(XML_SPACE, "preserve")
        parent.insert(idx, pre_r)
        idx += 1

    parent.insert(idx, del_el);  idx += 1
    parent.insert(idx, ins_el);  idx += 1

    if suffix:
        suf_r = copy.deepcopy(affected[-1][2])
        t_el = suf_r.find(f"{{{W}}}t")
        if t_el is None:
            t_el = OxmlElement("w:t")
            suf_r.append(t_el)
        t_el.text = suffix
        if suffix[0] == " " or suffix[-1] == " ":
            t_el.set(XML_SPACE, "preserve")
        parent.insert(idx, suf_r)

    return True


# ── Comentarios al margen ─────────────────────────────────────────────────────

def _add_comment_ref(para_el, comment_id: int) -> None:
    """Añade commentRangeStart/End y commentReference al párrafo."""
    start = OxmlElement("w:commentRangeStart")
    start.set(qn("w:id"), str(comment_id))
    end = OxmlElement("w:commentRangeEnd")
    end.set(qn("w:id"), str(comment_id))

    ref_r = OxmlElement("w:r")
    ref_rpr = OxmlElement("w:rPr")
    ref_style = OxmlElement("w:rStyle")
    ref_style.set(qn("w:val"), "CommentReference")
    ref_rpr.append(ref_style)
    ref_r.append(ref_rpr)
    ref = OxmlElement("w:commentReference")
    ref.set(qn("w:id"), str(comment_id))
    ref_r.append(ref)

    children = list(para_el)
    first_run_idx = next(
        (i for i, c in enumerate(children)
         if etree.QName(c).localname in ("r", "hyperlink", "ins", "del")),
        len(children) - 1,
    )
    para_el.insert(first_run_idx, start)
    para_el.append(end)
    para_el.append(ref_r)


def _build_comment_xml(comment_id: int, autor: str, texto: str, fecha: str) -> str:
    def esc(s: str) -> str:
        return (s.replace("&", "&amp;").replace("<", "&lt;")
                 .replace(">", "&gt;").replace('"', "&quot;"))

    paras = texto.split("\n")
    paras_xml = ""
    for i, p in enumerate(paras):
        paras_xml += f'<w:p><w:pPr><w:pStyle w:val="CommentText"/></w:pPr>'
        if i == 0:
            paras_xml += ('<w:r><w:rPr><w:rStyle w:val="CommentReference"/></w:rPr>'
                          '<w:annotationRef/></w:r>')
        paras_xml += f'<w:r><w:t xml:space="preserve">{esc(p)}</w:t></w:r></w:p>'

    return (f'<w:comment w:id="{comment_id}" w:author="{esc(autor)}" '
            f'w:date="{fecha}" w:initials="DIA">{paras_xml}</w:comment>')


def _inject_comments(docx_bytes: bytes, comment_xmls: list[str]) -> bytes:
    """Inyecta word/comments.xml en el zip del .docx."""
    inner = "\n".join(comment_xmls)
    comments_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"{inner}"
        "</w:comments>"
    )

    src = zipfile.ZipFile(io.BytesIO(docx_bytes), "r")
    out_buf = io.BytesIO()

    with zipfile.ZipFile(out_buf, "w", zipfile.ZIP_DEFLATED) as out:
        for item in src.infolist():
            data = src.read(item.filename)

            if item.filename == "word/_rels/document.xml.rels":
                text = data.decode("utf-8")
                if "comments" not in text.lower():
                    text = text.replace(
                        "</Relationships>",
                        '<Relationship Id="rIdComments" '
                        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/comments" '
                        'Target="comments.xml"/>\n</Relationships>',
                    )
                out.writestr(item, text.encode("utf-8"))

            elif item.filename == "[Content_Types].xml":
                text = data.decode("utf-8")
                if "comments" not in text.lower():
                    text = text.replace(
                        "</Types>",
                        '<Override PartName="/word/comments.xml" '
                        'ContentType="application/vnd.openxmlformats-officedocument'
                        '.wordprocessingml.comments+xml"/>\n</Types>',
                    )
                out.writestr(item, text.encode("utf-8"))

            else:
                out.writestr(item, data)

        out.writestr("word/comments.xml", comments_xml.encode("utf-8"))

    src.close()
    return out_buf.getvalue()


# ── Función principal ─────────────────────────────────────────────────────────

def generar_documento_revisado(docx_bytes: bytes, hallazgos: list) -> bytes:
    """
    Recibe bytes de .docx + lista de Hallazgo.
    Retorna bytes del .docx con track changes y comentarios insertados.
    """
    doc = Document(io.BytesIO(docx_bytes))
    rev_id = 200
    comment_id = 1
    comment_xmls: list[str] = []
    fecha = _now()

    for h in hallazgos:
        ubicacion = (h.ubicacion or "").strip()
        correccion = (h.correccion or "").strip()
        error = (h.error or "").strip()
        modulo = (h.modulo or "").strip()
        agente = h.agente
        severidad = h.severidad

        if not error and not ubicacion:
            continue

        autor = f"DISCIPLINAR[IA] — {agente} [{modulo}]"
        inserted_track = False

        # Agentes 1-3: intentar track change
        if (agente in AGENTES_TRACK
                and ubicacion and correccion
                and ubicacion.lower() != correccion.lower()):
            para_idx = _find_paragraph(doc, ubicacion)
            if para_idx is not None:
                try:
                    inserted_track = insertar_track_change(
                        doc, para_idx, ubicacion, correccion, autor, rev_id
                    )
                    if inserted_track:
                        rev_id += 2
                except Exception:
                    inserted_track = False

        # Agentes 4-5 siempre comentario; agentes 1-3 comentario si track falló
        if not inserted_track:
            sev_tag = {"alta": "[ALTA]", "media": "[MEDIA]", "baja": "[BAJA]"}.get(
                severidad, ""
            )
            lineas = [f"{sev_tag} {modulo}: {error}"]
            if ubicacion:
                lineas.append(f'Texto: "{ubicacion[:120]}"')
            if correccion:
                lineas.append(f"Sugerencia: {correccion}")
            texto_comentario = "\n".join(lineas)

            para_idx = _find_paragraph(doc, ubicacion) if ubicacion else None
            if para_idx is None:
                para_idx = max(0, len(doc.paragraphs) - 1)

            try:
                _add_comment_ref(doc.paragraphs[para_idx]._p, comment_id)
                comment_xmls.append(
                    _build_comment_xml(comment_id, autor, texto_comentario, fecha)
                )
                comment_id += 1
            except Exception:
                pass  # nunca interrumpir la exportación por un solo comentario

    # Guardar documento con track changes
    buf = io.BytesIO()
    doc.save(buf)
    result = buf.getvalue()

    # Inyectar comentarios si los hay
    if comment_xmls:
        result = _inject_comments(result, comment_xmls)

    return result
