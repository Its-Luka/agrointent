from __future__ import annotations

import hashlib
from difflib import get_close_matches
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


PyramidLevel = Literal["SURVIVAL", "DUTY", "OPPORTUNITY", "NEED", "ATTENTION_CYCLE"]

VALID_ACTIONS = {
    "emit_episode",
    "update_belief",
    "consume_resource",
    "send_event",
    "send_marketplace_event",
    "send_civic_land_request",
    "emit_emotion",
    "increase_health",
    "sync_clock",
    "log_audit",
    "increment_belief",
    "wait_for_event",
    "conditional",
    "send_society_collaboration",
    "spend_friends_time",
    "agro_ecosystem_operation",
    "set_land_crop_type",
}

VALID_OPERATION = {
    "PREPARE",
    "PLANT",
    "CHECK",
    "IRRIGATE",
    "PESTICIDE",
    "HARVEST",
    "DEFOREST",
    "SELL",
}

VALID_RESOURCE_KEYS = {
    "money",
    "time_left_on_day",
    "seeds",
    "water_available",
    "tools",
}

VALID_BELIEF_KEYS = {
    "money",
    "health",
    "happiness",
    "food_security",
    "social_capital",
    "days_in_crisis",
    "harvested_weight",
    "total_harvested_weight",
    "tools",
    "seeds",
    "water_available",
    "time_left_on_day",
    "last_crop_type",
    "resource_needed_type",
    "current_day",
    "price_list_available",
}

RESOURCE_KEY_ALIASES = {
    "water": "water_available",
    "agua": "water_available",
    "cash": "money",
    "dinero": "money",
    "seed": "seeds",
    "seeds": "seeds",
    "tool": "tools",
    "tools": "tools",
}

BELIEF_KEY_ALIASES = {
    "water": "water_available",
    "agua": "water_available",
    "cash": "money",
    "dinero": "money",
    "income": "money",
    "health": "health",
    "salud": "health",
    "drought_resistance": "food_security",
    "food": "food_security",
    "food_security": "food_security",
    "price_list": "price_list_available",
    "price_list_available": "price_list_available",
    "water_available": "water_available",
    "seeds": "seeds",
    "tools": "tools",
    "social": "social_capital",
}

OPERATION_ALIASES = {
    "irrigation": "IRRIGATE",
    "irrigate": "IRRIGATE",
    "regar": "IRRIGATE",
    "watering": "IRRIGATE",
    "planting": "PLANT",
    "plant": "PLANT",
    "sembrar": "PLANT",
    "sow": "PLANT",
    "prepare": "PREPARE",
    "preparar": "PREPARE",
    "check": "CHECK",
    "revisar": "CHECK",
    "harvest": "HARVEST",
    "cosechar": "HARVEST",
    "pesticide": "PESTICIDE",
    "fumigar": "PESTICIDE",
    "sell": "SELL",
    "vender": "SELL",
    "deforest": "DEFOREST",
    "deforestar": "DEFOREST",
}

DISPLAY_NAME_OVERRIDES = {
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
    "do_void": "Descansar",
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


class RawStep(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    action: Optional[str] = None
    args: dict = Field(default_factory=dict)


class RawGoal(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    version: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    pyramid_level: Optional[str] = None
    activation_when: Optional[str] = None
    plan_ref: Optional[str] = None
    contribution_rules: Optional[dict] = None
    emotion_tag: Optional[str] = None
    sub_level: Optional[str] = None
    effects: Optional[dict] = None
    normative_tags: Optional[list] = None


class RawPlan(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: Optional[str] = None
    version: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    goal_id: Optional[str] = None
    steps: list[RawStep] = Field(default_factory=list)
    on_timeout: list = Field(default_factory=list)
    on_failure: list = Field(default_factory=list)


class RawExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")
    goal: RawGoal = Field(default_factory=RawGoal)
    plan: RawPlan = Field(default_factory=RawPlan)


class ContributionRulesOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fixed_value: float = Field(0.5, ge=0.0, le=1.0)


class StepSpecOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    action: str
    args: dict = Field(default_factory=dict)

    @field_validator("action")
    @classmethod
    def action_must_be_valid(cls, v: str) -> str:
        if v not in VALID_ACTIONS:
            raise ValueError(f"Acción '{v}' no existe. Válidas: {sorted(VALID_ACTIONS)}")
        return v

    @field_validator("args")
    @classmethod
    def validate_args(cls, v: dict, info):
        action = info.data.get("action")
        if not action:
            return v

        if action == "agro_ecosystem_operation":
            op = str(v.get("operation", "")).upper().strip()
            if op not in VALID_OPERATION:
                raise ValueError(f"operation inválida: {op}. Válidas: {sorted(VALID_OPERATION)}")
            if "crop_type" not in v or not str(v.get("crop_type", "")).strip():
                raise ValueError("agro_ecosystem_operation requiere crop_type.")

        elif action == "consume_resource":
            key = str(v.get("key", "")).strip()
            if key not in VALID_RESOURCE_KEYS:
                raise ValueError(f"key inválida en consume_resource: {key}")

        elif action == "increment_belief":
            key = str(v.get("key", "")).strip()
            if key not in VALID_BELIEF_KEYS:
                raise ValueError(f"key inválida en increment_belief: {key}")

        elif action == "emit_emotion":
            axis = str(v.get("axis", "")).strip().lower()
            if axis not in {"happiness", "hopeful", "secure"}:
                raise ValueError(f"axis inválida en emit_emotion: {axis}")

        return v


class GoalSpecOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    description: str
    pyramid_level: PyramidLevel
    activation_when: str
    plan_ref: str
    contribution_rules: ContributionRulesOut = Field(default_factory=ContributionRulesOut)
    emotion_tag: str = "neutral"


class PlanSpecOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    display_name: str
    description: str
    goal_id: str
    steps: list[StepSpecOut]


class ExtractionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    goal: GoalSpecOut
    plan: PlanSpecOut

    def relink(self) -> "ExtractionResult":
        self.goal.plan_ref = self.plan.id
        self.plan.goal_id = self.goal.id
        return self


def _humanize(identifier: str) -> str:
    text = identifier.replace("_", " ").replace("-", " ").strip()
    return text.title() if text else "Meta agrícola"


def _stable_goal_id(seed: str) -> str:
    digest = hashlib.sha1(seed.encode("utf-8")).hexdigest()[:8]
    return f"goal_{digest}"


def _normalize_operation(operation: str | None) -> str:
    if not operation:
        return "CHECK"
    raw = str(operation).strip()
    up = raw.upper()
    low = raw.lower()
    if up in VALID_OPERATION:
        return up
    if low in OPERATION_ALIASES:
        return OPERATION_ALIASES[low]
    matches = get_close_matches(up, sorted(VALID_OPERATION), n=1, cutoff=0.75)
    return matches[0] if matches else "CHECK"


def _normalize_key(key: str | None, aliases: dict[str, str], valid_set: set[str], default: str) -> str:
    if not key:
        return default
    raw = str(key).strip()
    low = raw.lower()
    if raw in valid_set:
        return raw
    if low in aliases:
        return aliases[low]
    matches = get_close_matches(raw, sorted(valid_set), n=1, cutoff=0.75)
    return matches[0] if matches else default


def _normalize_args(action: str, args: dict) -> dict:
    args = dict(args or {})

    if action == "agro_ecosystem_operation":
        args["operation"] = _normalize_operation(args.get("operation"))
        crop = args.get("crop_type")
        if crop is None or not str(crop).strip():
            args["crop_type"] = "maiz"
        else:
            args["crop_type"] = str(crop).strip().replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")

    elif action == "consume_resource":
        args["key"] = _normalize_key(args.get("key"), RESOURCE_KEY_ALIASES, VALID_RESOURCE_KEYS, "water_available")
        if "amount" not in args or args["amount"] in (None, ""):
            args["amount"] = 1

    elif action == "increment_belief":
        args["key"] = _normalize_key(args.get("key"), BELIEF_KEY_ALIASES, VALID_BELIEF_KEYS, "food_security")
        if "amount" not in args or args["amount"] in (None, ""):
            args["amount"] = 1

    elif action == "update_belief":
        if "key" in args:
            args["key"] = _normalize_key(args.get("key"), BELIEF_KEY_ALIASES, VALID_BELIEF_KEYS, "food_security")
        if "value" not in args:
            args["value"] = True

    elif action == "emit_emotion":
        axis = str(args.get("axis", "happiness")).strip().lower()
        if axis not in {"happiness", "hopeful", "secure"}:
            axis = "happiness"
        args["axis"] = axis
        if "delta" not in args or args["delta"] in (None, ""):
            args["delta"] = 0.1

    return args


def _display_name(goal_id: str, provided: str | None = None) -> str:
    if provided and provided.strip():
        return provided.strip()
    if goal_id in DISPLAY_NAME_OVERRIDES:
        return DISPLAY_NAME_OVERRIDES[goal_id]
    return _humanize(goal_id)


def repair(raw: RawExtraction) -> dict:
    g, p = raw.goal, raw.plan

    goal_id = g.id or _stable_goal_id(g.activation_when or "crisis")
    plan_id = p.id or f"{goal_id}_plan"

    goal = {
        "id": goal_id,
        "display_name": _display_name(goal_id, g.display_name),
        "description": g.description or f"Meta generada a partir de: {g.activation_when or 'la narrativa proporcionada'}",
        "pyramid_level": (g.pyramid_level or "NEED").upper(),
        "activation_when": g.activation_when or "belief.get('days_in_crisis') > 0",
        "plan_ref": plan_id,
        "contribution_rules": {
            "fixed_value": (g.contribution_rules or {}).get("fixed_value", 0.5)
        },
        "emotion_tag": g.emotion_tag or "neutral",
    }

    steps = []
    for i, s in enumerate(p.steps, start=1):
        action = s.action or "emit_episode"
        if action not in VALID_ACTIONS:
            matches = get_close_matches(action, sorted(VALID_ACTIONS), n=1, cutoff=0.85)
            action = matches[0] if matches else "emit_episode"
        steps.append(
            {
                "id": s.id or f"step_{i}",
                "action": action,
                "args": _normalize_args(action, s.args or {}),
            }
        )

    plan = {
        "id": plan_id,
        "display_name": p.display_name or _humanize(plan_id),
        "description": p.description or f"Plan de acción para {goal['display_name']}",
        "goal_id": goal_id,
        "steps": steps,
    }

    return {"goal": goal, "plan": plan}