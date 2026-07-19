from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

STOPWORDS = {
    "a", "acá", "ahí", "al", "algo", "algunas", "algunos", "ante", "antes", "aqui", "así",
    "como", "con", "contra", "cual", "cuando", "de", "del", "desde", "donde", "dos",
    "e", "el", "ella", "ellas", "ellos", "en", "entre", "era", "eramos", "eran", "eres",
    "es", "esa", "ese", "eso", "esta", "este", "estos", "está", "están", "fue",
    "ha", "haber", "hay", "la", "las", "le", "les", "lo", "los", "mas", "más", "me",
    "mi", "mis", "muy", "no", "nos", "nosotros", "o", "otra", "otro", "para", "pero",
    "por", "porque", "qué", "que", "se", "si", "sí", "sin", "sobre", "su", "sus", "te",
    "tiene", "tienen", "todo", "todos", "tu", "tus", "un", "una", "uno", "unos", "y",
    "ya", "yo", "ser", "estar", "debe", "deben", "puede", "pueden",
    "hacer", "haciendo", "también", "tambien",
}


@dataclass
class ContextSummary:
    file_name: str
    title: str
    summary: str
    key_points: list[str]
    pending_items: list[str]
    keywords: list[str]
    problems_detected: list[str] = field(default_factory=list)
    objectives_possible: list[str] = field(default_factory=list)
    actions_suggested: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    crops: list[str] = field(default_factory=list)
    resources: list[str] = field(default_factory=list)
    mode: str = "heuristic"

    def to_dict(self) -> dict[str, Any]:
        return {
            "file_name": self.file_name,
            "title": self.title,
            "summary": self.summary,
            "key_points": self.key_points,
            "pending_items": self.pending_items,
            "keywords": self.keywords,
            "problems_detected": self.problems_detected,
            "objectives_possible": self.objectives_possible,
            "actions_suggested": self.actions_suggested,
            "risks": self.risks,
            "crops": self.crops,
            "resources": self.resources,
            "mode": self.mode,
        }

    def to_markdown(self) -> str:
        def _block(title: str, items: list[str]) -> str:
            if not items:
                return f"## {title}\n- (sin datos detectados)\n"
            return f"## {title}\n" + "\n".join(f"- {x}" for x in items) + "\n"

        return (
            f"# {self.title}\n\n"
            f"**Archivo:** {self.file_name}\n\n"
            f"**Modo de resumen:** {self.mode}\n\n"
            f"## Resumen\n{self.summary}\n\n"
            f"{_block('Puntos clave', self.key_points)}\n"
            f"{_block('Pendientes / señales de trabajo', self.pending_items)}\n"
            f"{_block('Problemas detectados', self.problems_detected)}\n"
            f"{_block('Objetivos posibles', self.objectives_possible)}\n"
            f"{_block('Acciones sugeridas', self.actions_suggested)}\n"
            f"{_block('Riesgos', self.risks)}\n"
            f"{_block('Cultivos', self.crops)}\n"
            f"{_block('Recursos', self.resources)}\n"
            f"## Palabras clave\n"
            + (", ".join(self.keywords) if self.keywords else "(sin palabras clave)")
            + "\n"
        )


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_spaces(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def markdown_to_plain_text(md: str) -> str:
    text = md or ""
    text = re.sub(r"```.*?```", "", text, flags=re.S)
    text = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*+]\s*", "- ", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s*", "- ", text, flags=re.M)
    text = text.replace("**", "").replace("__", "").replace("~~", "")
    text = _normalize_spaces(text)
    return text


def _first_heading(text: str) -> str | None:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return None


def _paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _extract_keywords(text: str, top_n: int = 10) -> list[str]:
    norm = _strip_accents(text.lower())
    tokens = re.findall(r"[a-záéíóúñü]{4,}", norm, flags=re.I)
    filtered = [t for t in tokens if t not in STOPWORDS]
    counts = Counter(filtered)
    return [word for word, _ in counts.most_common(top_n)]


def _extract_bullet_like_lines(text: str) -> list[str]:
    lines = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(("-", "*", "+")):
            item = line.lstrip("-*+").strip()
            if item:
                lines.append(item)
        elif re.match(r"^\d+\.", line):
            item = re.sub(r"^\d+\.\s*", "", line).strip()
            if item:
                lines.append(item)
    return lines


def _extract_pending_lines(text: str) -> list[str]:
    pending_markers = (
        "pendiente", "pendientes", "falta", "faltan", "debe", "deben",
        "hay que", "se debe", "conviene", "por hacer", "to do", "todo",
        "modificar", "crear", "reemplazar", "ajustar", "corregir", "revisar",
        "problema", "riesgo", "objetivo", "solución", "solucion",
    )
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        low = line.lower()
        if not line:
            continue
        if any(marker in low for marker in pending_markers):
            out.append(line)
    return out


def _shorten(text: str, max_words: int = 120) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text.strip()
    return " ".join(words[:max_words]).strip() + "..."


def _load_yaml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_domain_terms() -> dict[str, set[str]]:
    base = Path(__file__).resolve().parent
    resources = base / "resources"
    files_dir = base / "files"

    terms = {
        "crops": set(),
        "hazards": set(),
        "resources": set(),
        "regions": set(),
    }

    # crops.yaml
    crops = _load_yaml(resources / "crops.yaml")
    for k, v in (crops.get("engine_recognized") or {}).items():
        terms["crops"].add(str(k).lower())
        for item in v or []:
            terms["crops"].add(str(item).lower())
    for item in (crops.get("narrative_only") or []):
        terms["crops"].add(str(item).lower())

    # hazards.yaml
    hazards = _load_yaml(resources / "hazards.yaml")
    for item in (hazards.get("engine_events") or []):
        if isinstance(item, dict):
            if item.get("event_type"):
                terms["hazards"].add(str(item["event_type"]).lower())
            if item.get("es"):
                terms["hazards"].add(str(item["es"]).lower())
    for item in (hazards.get("regional_narrative_only") or []):
        terms["hazards"].add(str(item).lower())

    # ontology.yaml
    ontology = _load_yaml(resources / "ontology.yaml")
    for entity, data in (ontology.get("entities") or {}).items():
        terms["resources"].add(str(entity).lower())
        if isinstance(data, dict):
            for s in data.get("synonyms", []) or []:
                terms["resources"].add(str(s).lower())
            for s in data.get("resources", []) or []:
                terms["resources"].add(str(s).lower())
            for s in data.get("problems", []) or []:
                terms["hazards"].add(str(s).lower())
            for s in data.get("actions", []) or []:
                terms["resources"].add(str(s).lower())

    # municipalities.yaml
    municipalities = _load_yaml(resources / "municipalities.yaml")
    for region in municipalities.get("regions", []) or []:
        if not isinstance(region, dict):
            continue
        if region.get("name"):
            terms["regions"].add(str(region["name"]).lower())
        for alias in region.get("aliases", []) or []:
            terms["regions"].add(str(alias).lower())
        for crop in region.get("crops", []) or []:
            terms["crops"].add(str(crop).lower())
        for problem in region.get("problems", []) or []:
            terms["hazards"].add(str(problem).lower())

    # fallback local vocabulary
    vocab = _load_yaml(resources / "vocabulary.yaml")
    for item in vocab.get("terms", []) or []:
        if not isinstance(item, dict):
            continue
        if item.get("term"):
            terms["resources"].add(str(item["term"]).lower())

    # if no resources file exists, use a conservative fallback
    terms["resources"].update(
        {
            "agua", "semillas", "apoyo", "crédito", "credito", "pipas",
            "cisternas", "tanques", "pozo", "forraje", "fertilizante", "gasolina",
            "equipo", "riego", "ayuda",
        }
    )
    terms["hazards"].update(
        {
            "sequía", "sequia", "plaga", "extorsión", "extorsion",
            "costos altos", "falta de agua", "inundación", "inundacion", "helada",
            "granizada", "siniestros agroclimáticos", "siniestros_agroclimaticos",
        }
    )
    terms["crops"].update(
        {
            "maiz", "maíz", "frijol", "ganado", "flores", "cafe", "café", "avena",
            "trigo", "cebada", "haba", "papa", "alfalfa", "nopal", "calabaza",
            "jitomate",
        }
    )
    return terms


DOMAIN_TERMS = _load_domain_terms()


def _find_terms(text: str, candidates: set[str]) -> list[str]:
    norm = _strip_accents(text.lower())
    found = []
    for term in sorted(candidates, key=len, reverse=True):
        tnorm = _strip_accents(term.lower()).strip()
        if not tnorm:
            continue
        if tnorm in norm and term not in found:
            found.append(term)
    return found


def _problem_sentences(text: str) -> list[str]:
    markers = (
        "sequía", "sequia", "plaga", "extors", "precio", "costos", "crédito", "credito",
        "seguro", "falta de agua", "escasez", "inund", "helada", "granizada",
        "ganado", "forraje", "pozo", "cisterna", "pipa", "apoyo", "ayuda",
    )
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        s = sentence.strip()
        if not s:
            continue
        low = _strip_accents(s.lower())
        if any(_strip_accents(m) in low for m in markers):
            out.append(_shorten(s, max_words=18))
    return out[:8]


def _objectives_possible(text: str, crops: list[str], risks: list[str]) -> list[str]:
    norm = _strip_accents(text.lower())
    out = []

    if any(x in norm for x in ("agua", "riego", "pipa", "cisterna", "tanque", "pozo")):
        out.append("Garantizar el abastecimiento de agua")
    if any(x in norm for x in ("plaga", "gusano", "barrenador", "fumigar")):
        out.append("Controlar la plaga o enfermedad")
    if any(x in norm for x in ("crédito", "credito", "apoyo", "financiamiento", "seguro")):
        out.append("Obtener apoyo o financiamiento")
    if any(x in norm for x in ("precio", "mercado", "coyote", "venta")):
        out.append("Mejorar el precio de venta")
    if any(x in norm for x in ("extors", "delinc", "piso")):
        out.append("Reducir el impacto de la extorsión")
    if crops:
        out.append(f"Proteger el cultivo de {crops[0]}")
    if risks and "Sequía" in risks:
        out.append("Mitigar el impacto de la sequía")
    return list(dict.fromkeys(out))[:6]


def _actions_suggested(text: str, crops: list[str], risks: list[str]) -> list[str]:
    norm = _strip_accents(text.lower())
    out = []

    if any(x in norm for x in ("agua", "riego", "pipa", "cisterna", "tanque", "pozo")):
        out.extend([
            "Buscar pipas o fuentes de agua adicionales",
            "Almacenar agua en tanques o cisternas",
            "Gestionar apoyo para un pozo o mejor abastecimiento",
        ])
    if any(x in norm for x in ("plaga", "gusano", "barrenador", "fumigar")):
        out.append("Solicitar control zoosanitario o fumigación")
    if any(x in norm for x in ("crédito", "credito", "apoyo", "seguro", "financiamiento")):
        out.append("Solicitar crédito, seguro o apoyo gubernamental")
    if any(x in norm for x in ("precio", "mercado", "coyote", "venta")):
        out.append("Buscar mejor comprador o negociar precios")
    if any(x in norm for x in ("extors", "delinc", "piso")):
        out.append("Buscar apoyo comunitario o institucional")
    if crops:
        out.append(f"Priorizar medidas para {crops[0]}")
    if risks:
        out.append("Reducir la exposición al riesgo identificado")

    return list(dict.fromkeys(out))[:8]


def _risks(text: str) -> list[str]:
    found = _find_terms(text, DOMAIN_TERMS["hazards"])
    if not found:
        return []
    # Pretty-print a bit
    pretty = []
    for item in found:
        if item not in pretty:
            pretty.append(item)
    return pretty[:10]


def _crops(text: str) -> list[str]:
    found = _find_terms(text, DOMAIN_TERMS["crops"])
    return found[:10]


def _resources(text: str) -> list[str]:
    found = _find_terms(text, DOMAIN_TERMS["resources"])
    return found[:10]


def _heuristic_summary(file_name: str, text: str) -> ContextSummary:
    heading = _first_heading(text) or Path(file_name).stem.replace("_", " ").replace("-", " ").title()
    paragraphs = _paragraphs(text)
    summary_source = " ".join(paragraphs[:2]) if paragraphs else text
    summary = _shorten(summary_source, max_words=140)

    bullets = _extract_bullet_like_lines(text)
    key_points = bullets[:6] if bullets else []
    if not key_points and paragraphs:
        key_points = [_shorten(p, max_words=20) for p in paragraphs[:4]]

    pending_items = _extract_pending_lines(text)[:8]
    keywords = _extract_keywords(text, top_n=10)
    problems = _problem_sentences(text)
    crops = _crops(text)
    risks = _risks(text)
    resources = _resources(text)
    objectives = _objectives_possible(text, crops, risks)
    actions = _actions_suggested(text, crops, risks)

    return ContextSummary(
        file_name=file_name,
        title=heading,
        summary=summary or "No se pudo generar un resumen heurístico.",
        key_points=key_points,
        pending_items=pending_items,
        keywords=keywords,
        problems_detected=problems,
        objectives_possible=objectives,
        actions_suggested=actions,
        risks=risks,
        crops=crops,
        resources=resources,
        mode="heuristic",
    )


def _get_client():
    try:
        from groq import Groq
    except ModuleNotFoundError:
        return None

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        return None

    return Groq(api_key=api_key)


def _llm_summary_prompt(file_name: str, text: str) -> list[dict[str, str]]:
    system = (
        "Eres un analista técnico y resumidor de contexto para un proyecto de software agrícola. "
        "Tu tarea es leer un archivo markdown o texto y producir un resumen útil y breve, "
        "orientado a desarrollo y análisis de problemáticas. Debes identificar: objetivo del documento, "
        "decisiones, problemas, riesgos, cultivos, recursos, acciones sugeridas y palabras clave. "
        "Responde SOLO JSON válido y nada más."
    )
    user = f"""
Archivo: {file_name}

Texto:
{text}

Devuelve un JSON con esta forma exacta:
{{
  "title": "título corto",
  "summary": "resumen de 4 a 8 oraciones",
  "key_points": ["punto 1", "punto 2"],
  "pending_items": ["pendiente 1", "pendiente 2"],
  "problems_detected": ["problema 1", "problema 2"],
  "objectives_possible": ["objetivo 1", "objetivo 2"],
  "actions_suggested": ["acción 1", "acción 2"],
  "risks": ["riesgo 1", "riesgo 2"],
  "crops": ["cultivo 1", "cultivo 2"],
  "resources": ["recurso 1", "recurso 2"],
  "keywords": ["palabra1", "palabra2", "palabra3"]
}}
""".strip()
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]


def _parse_json_response(text: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text)
        return obj if isinstance(obj, dict) else None
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            return None
        try:
            obj = json.loads(m.group(0))
            return obj if isinstance(obj, dict) else None
        except Exception:
            return None


def _llm_or_heuristic(file_name: str, plain_text: str) -> ContextSummary:
    if len(plain_text) > 30000:
        summary = _heuristic_summary(file_name, plain_text)
        summary.mode = "heuristic-long-file"
        return summary

    client = _get_client()
    if client is None:
        return _heuristic_summary(file_name, plain_text)

    try:
        model_name = os.getenv("AGROINTENT_SUMMARY_MODEL", os.getenv("AGROINTENT_MODEL", "llama-3.3-70b-versatile"))
        response = client.chat.completions.create(
            model=model_name,
            temperature=0.15,
            response_format={"type": "json_object"},
            messages=_llm_summary_prompt(file_name, plain_text[:28000]),
        )
        content = response.choices[0].message.content or ""
        parsed = _parse_json_response(content)
        if not parsed:
            return _heuristic_summary(file_name, plain_text)

        title = str(parsed.get("title") or Path(file_name).stem.replace("_", " ").title())
        summary = str(parsed.get("summary") or "").strip() or "No se obtuvo resumen del modelo."

        def _list(name: str) -> list[str]:
            value = parsed.get(name) or []
            if not isinstance(value, list):
                return []
            return [str(x) for x in value if str(x).strip()][:10]

        return ContextSummary(
            file_name=file_name,
            title=title,
            summary=summary,
            key_points=_list("key_points"),
            pending_items=_list("pending_items"),
            problems_detected=_list("problems_detected"),
            objectives_possible=_list("objectives_possible"),
            actions_suggested=_list("actions_suggested"),
            risks=_list("risks"),
            crops=_list("crops"),
            resources=_list("resources"),
            keywords=_list("keywords")[:12],
            mode=f"llm:{model_name}",
        )
    except Exception:
        return _heuristic_summary(file_name, plain_text)


def summarize_uploaded_context(file_name: str, raw_text: str) -> ContextSummary:
    plain = markdown_to_plain_text(raw_text)
    if not plain.strip():
        return ContextSummary(
            file_name=file_name,
            title=Path(file_name).stem.replace("_", " ").title(),
            summary="El archivo estaba vacío o no se pudo leer correctamente.",
            key_points=[],
            pending_items=[],
            keywords=[],
            problems_detected=[],
            objectives_possible=[],
            actions_suggested=[],
            risks=[],
            crops=[],
            resources=[],
            mode="empty",
        )
    return _llm_or_heuristic(file_name, plain)