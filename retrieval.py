from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
import json
import re
import unicodedata
from typing import Iterable, Any

import yaml


DISPLAY_OVERRIDES = {
    "plant_crop": "Sembrar cultivo",
    "prepare_land": "Preparar terreno",
    "irrigate_crops": "Regar cultivos",
    "manage_pests": "Controlar plagas",
    "harvest_crops": "Cosechar cultivos",
    "sell_crop": "Vender cosecha",
    "obtain_water": "Obtener agua",
    "obtain_seeds": "Obtener semillas",
    "obtain_tools": "Obtener herramientas",
    "obtain_supplies": "Obtener insumos",
    "obtain_pesticides": "Obtener pesticidas",
    "obtain_livestock": "Obtener ganado",
    "obtain_a_land": "Obtener tierra",
    "look_for_loan": "Buscar préstamo",
    "pay_debts": "Pagar deudas",
    "search_for_help": "Buscar ayuda",
    "community_meeting": "Reunión comunitaria",
    "communicate": "Comunicación",
    "look_for_collaboration": "Buscar colaboración",
    "provide_collaboration": "Brindar colaboración",
    "work_for_other": "Trabajar para otro",
    "do_healthcare": "Atención médica",
    "do_vitals": "Cubrir necesidades básicas",
    "do_void": "Descansar / vaciar necesidad",
    "seek_purpose": "Buscar propósito",
    "self_evaluation": "Autoevaluación",
    "alternative_work": "Trabajo alternativo",
    "get_price_list": "Consultar precios",
    "get_training": "Recibir capacitación",
    "find_news": "Buscar noticias",
    "leisure_activities": "Actividades de ocio",
    "spend_family_time": "Tiempo en familia",
    "spend_friends_time": "Tiempo con amistades",
    "waste_time_and_resources": "Perder tiempo y recursos",
    "attend_religious_events": "Asistir a eventos religiosos",
    "deforest_land": "Deforestar terreno",
}

KEYWORD_BOOSTS = {
    "sequia": {"irrigate_crops", "obtain_water", "prepare_land", "plant_crop", "look_for_loan"},
    "drought": {"irrigate_crops", "obtain_water", "prepare_land", "plant_crop", "look_for_loan"},
    "agua": {"irrigate_crops", "obtain_water"},
    "riego": {"irrigate_crops", "obtain_water"},
    "semilla": {"obtain_seeds", "plant_crop"},
    "semillas": {"obtain_seeds", "plant_crop"},
    "siembra": {"plant_crop", "prepare_land", "obtain_seeds"},
    "cultivo": {"plant_crop", "harvest_crops", "irrigate_crops", "manage_pests"},
    "cosecha": {"harvest_crops", "sell_crop"},
    "cosechar": {"harvest_crops"},
    "plaga": {"manage_pests", "obtain_pesticides"},
    "pest": {"manage_pests", "obtain_pesticides"},
    "fumigar": {"manage_pests", "obtain_pesticides"},
    "helada": {"harvest_crops", "sell_crop", "search_for_help"},
    "granizada": {"harvest_crops", "search_for_help"},
    "deuda": {"pay_debts", "look_for_loan", "search_for_help"},
    "prestamo": {"look_for_loan", "pay_debts"},
    "préstamo": {"look_for_loan", "pay_debts"},
    "dinero": {"look_for_loan", "pay_debts", "sell_crop", "get_price_list"},
    "mercado": {"sell_crop", "get_price_list"},
    "coyote": {"sell_crop", "get_price_list"},
    "tequio": {"community_meeting", "look_for_collaboration", "provide_collaboration"},
    "comunidad": {"community_meeting", "look_for_collaboration", "provide_collaboration"},
    "salud": {"do_healthcare"},
    "enfermo": {"do_healthcare"},
    "enferma": {"do_healthcare"},
    "trabajo": {"alternative_work", "work_for_other"},
    "jornalero": {"alternative_work", "work_for_other", "do_healthcare"},
    "ejido": {"send_civic_land_request", "community_meeting"},
    "milpa": {"plant_crop", "prepare_land", "harvest_crops", "irrigate_crops"},
    "temporal": {"plant_crop", "prepare_land"},
    "sembrar": {"plant_crop"},
    "regar": {"irrigate_crops"},
    "cosechar": {"harvest_crops"},
    "vender": {"sell_crop"},
}

LOCALIZED_RENAMES = {
    "plant_crop": "Sembrar cultivo",
    "prepare_land": "Preparar terreno",
    "irrigate_crops": "Regar cultivos",
    "manage_pests": "Controlar plagas",
    "harvest_crops": "Cosechar cultivos",
    "sell_crop": "Vender cosecha",
    "obtain_water": "Obtener agua",
    "obtain_seeds": "Obtener semillas",
    "obtain_tools": "Obtener herramientas",
    "obtain_supplies": "Obtener insumos",
    "look_for_loan": "Buscar préstamo",
    "pay_debts": "Pagar deudas",
    "search_for_help": "Buscar ayuda",
    "community_meeting": "Reunión comunitaria",
    "look_for_collaboration": "Buscar colaboración",
    "provide_collaboration": "Brindar colaboración",
    "work_for_other": "Trabajar para otro",
    "alternative_work": "Trabajo alternativo",
    "get_price_list": "Consultar precios",
    "get_training": "Recibir capacitación",
    "do_healthcare": "Atención médica",
    "do_vitals": "Cubrir necesidades básicas",
    "do_void": "Descansar",
    "seek_purpose": "Buscar propósito",
    "self_evaluation": "Autoevaluación",
}


@dataclass(frozen=True)
class Candidate:
    goal_id: str
    plan_id: str
    display_name: str
    description: str
    activation_when: str
    category: str
    score: float = 0.0


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_text(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = re.sub(r"[^a-z0-9_ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _tokenize(text: str) -> set[str]:
    normalized = _normalize_text(text)
    return set(normalized.split()) if normalized else set()


def _jaccard(a: Iterable[str], b: Iterable[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def _human_goal_label(goal_id: str, display_name: str | None = None) -> str:
    if goal_id in LOCALIZED_RENAMES:
        return LOCALIZED_RENAMES[goal_id]
    if display_name and display_name.strip():
        return display_name.strip()
    return goal_id.replace("_", " ").replace("-", " ").title()


def _load_yaml(path: Path) -> dict[str, Any]:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def _load_json(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _extract_goal_item(item: dict[str, Any]) -> Candidate | None:
    goal_id = str(item.get("id") or "").strip()
    plan_ref = str(item.get("plan_ref") or "").strip()
    if not goal_id:
        return None
    return Candidate(
        goal_id=goal_id,
        plan_id=plan_ref or f"{goal_id}_plan",
        display_name=_human_goal_label(goal_id, str(item.get("display_name") or "")),
        description=str(item.get("description") or ""),
        activation_when=str(item.get("activation_when") or ""),
        category=str(item.get("category") or item.get("group") or ""),
        score=0.0,
    )


@lru_cache(maxsize=8)
def load_corpus_index(base_dir: str = "files", knowledge_dir: str = "knowledge") -> list[Candidate]:
    """
    Carga candidatos desde knowledge/ si existe.
    Si no existe, hace fallback a recorrer files/goals + files/plans.
    """
    base = Path(base_dir)
    kdir = Path(knowledge_dir)

    # 1) Intentar índices JSON primero
    goal_index_path = kdir / "goal_index.json"
    plan_index_path = kdir / "plan_index.json"

    if goal_index_path.exists() and plan_index_path.exists():
        goals = _load_json(goal_index_path)
        plans = _load_json(plan_index_path)

        plans_by_id = {str(p.get("id") or "").strip(): p for p in plans if p.get("id")}
        candidates: list[Candidate] = []

        for g in goals:
            goal_id = str(g.get("id") or "").strip()
            if not goal_id:
                continue

            plan_ref = str(g.get("plan_ref") or "").strip()
            plan = plans_by_id.get(plan_ref) or {}

            candidates.append(
                Candidate(
                    goal_id=goal_id,
                    plan_id=plan_ref or f"{goal_id}_plan",
                    display_name=_human_goal_label(goal_id, str(g.get("display_name") or "")),
                    description=str(g.get("description") or ""),
                    activation_when=str(g.get("activation_when") or ""),
                    category=str(g.get("category") or ""),
                    score=0.0,
                )
            )

        if candidates:
            return candidates

    # 2) Fallback a files/
    goals_root = base / "goals"
    plans_root = base / "plans"
    candidates: list[Candidate] = []

    if not goals_root.exists() or not plans_root.exists():
        return candidates

    for goal_file in goals_root.rglob("*.yaml"):
        goal = _load_yaml(goal_file)
        goal_id = str(goal.get("id") or "").strip()
        if not goal_id:
            continue

        category = goal_file.parent.name
        plan_file = plans_root / category / f"{goal_id}.yaml"
        if not plan_file.exists():
            plan_file = plans_root / category / f"{goal_id}_plan.yaml"
        if not plan_file.exists():
            continue

        candidates.append(
            Candidate(
                goal_id=goal_id,
                plan_id=str((goal.get("plan_ref") or plan_file.stem)).strip(),
                display_name=_human_goal_label(goal_id, str(goal.get("display_name") or "")),
                description=str(goal.get("description") or ""),
                activation_when=str(goal.get("activation_when") or ""),
                category=category,
                score=0.0,
            )
        )

    return candidates


def rank_candidates(narrative: str, candidates: list[Candidate], top_k: int = 5) -> list[Candidate]:
    narrative_norm = _normalize_text(narrative)
    narrative_tokens = _tokenize(narrative)
    ranked: list[Candidate] = []

    for c in candidates:
        title_tokens = _tokenize(c.display_name)
        desc_tokens = _tokenize(c.description)
        act_tokens = _tokenize(c.activation_when)
        id_tokens = _tokenize(c.goal_id)

        score = 0.0
        score += 0.30 * _jaccard(narrative_tokens, title_tokens)
        score += 0.35 * _jaccard(narrative_tokens, desc_tokens)
        score += 0.20 * _jaccard(narrative_tokens, act_tokens)
        score += 0.15 * _jaccard(narrative_tokens, id_tokens)

        for keyword, ids in KEYWORD_BOOSTS.items():
            if keyword in narrative_norm and c.goal_id in ids:
                score += 0.18

        if any(term in narrative_norm for term in ("maiz", "milpa", "temporal", "ejido", "tequio", "coyote", "jornalero")):
            if c.category == "agro":
                score += 0.05

        ranked.append(
            Candidate(
                goal_id=c.goal_id,
                plan_id=c.plan_id,
                display_name=c.display_name,
                description=c.description,
                activation_when=c.activation_when,
                category=c.category,
                score=round(score, 4),
            )
        )

    ranked.sort(key=lambda x: x.score, reverse=True)
    return ranked[:top_k]


def render_candidates(candidates: list[Candidate]) -> str:
    if not candidates:
        return "No hay candidatos recuperados."

    lines = []
    for idx, c in enumerate(candidates, start=1):
        lines.append(
            f"{idx}. goal_id={c.goal_id} | plan_id={c.plan_id} | "
            f"title={c.display_name} | category={c.category} | score={c.score:.3f} | "
            f"activation_when={c.activation_when}"
        )
    return "\n".join(lines)