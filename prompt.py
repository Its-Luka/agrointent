from __future__ import annotations

from pathlib import Path
import yaml

BASE_DIR = Path(__file__).resolve().parent
FILES_DIR = BASE_DIR / "files"
RESOURCES_DIR = BASE_DIR / "resources"
FEWSHOT_PATH = BASE_DIR / "prompts" / "fewshot.md"


def _safe_read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""


def _load_yaml(path: Path) -> dict:
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except FileNotFoundError:
        return {}


def _render_actions_doc() -> str:
    return """
Acciones válidas y formato esperado:

- agro_ecosystem_operation:
  args:
    operation: PREPARE | PLANT | CHECK | IRRIGATE | PESTICIDE | HARVEST | DEFOREST | SELL
    crop_type: cultivo mencionado por la narrativa

- set_land_crop_type:
  args:
    crop_type: cultivo

- consume_resource:
  args:
    key: money | time_left_on_day | seeds | water_available | tools
    amount: número

- increment_belief:
  args:
    key: money | health | happiness | food_security | social_capital | days_in_crisis | harvested_weight | total_harvested_weight | tools | seeds | water_available | time_left_on_day | last_crop_type | resource_needed_type | current_day | price_list_available
    amount: número

- update_belief:
  args:
    key: creencia válida
    value: cualquier valor razonable

- increase_health:
  args: {}

- emit_episode:
  args:
    text: texto narrativo
    tags: lista de tags

- emit_emotion:
  args:
    axis: happiness | hopeful | secure
    delta: número entre -1 y 1

- send_society_collaboration:
  args: {}

- spend_friends_time:
  args: {}

- send_marketplace_event:
  args: {}

- send_civic_land_request:
  args: {}

- send_event:
  args: {}

- sync_clock:
  args: {}

- log_audit:
  args: {}

- wait_for_event:
  args: {}

- conditional:
  args: {}
""".strip()


def _render_domain_hints() -> str:
    crops = _load_yaml(RESOURCES_DIR / "crops.yaml")
    hazards = _load_yaml(RESOURCES_DIR / "hazards.yaml")
    vocab = _load_yaml(RESOURCES_DIR / "vocabulary.yaml")
    ontology = _load_yaml(RESOURCES_DIR / "ontology.yaml")
    municipalities = _load_yaml(RESOURCES_DIR / "municipalities.yaml")

    crop_lines = []
    for k, v in (crops.get("engine_recognized") or {}).items():
        crop_lines.append(f"- {k}: {', '.join(v)}")

    hazard_lines = []
    for item in (hazards.get("engine_events") or []):
        hazard_lines.append(f"- {item.get('event_type')}: {item.get('es')}")

    vocab_terms = []
    for item in (vocab.get("terms") or [])[:20]:
        vocab_terms.append(f"- {item.get('term')}: {item.get('meaning')}")

    ontology_lines = []
    for entity, data in (ontology.get("entities") or {}).items():
        synonyms = ", ".join(data.get("synonyms", [])) if isinstance(data, dict) else ""
        problems = ", ".join(data.get("problems", [])) if isinstance(data, dict) else ""
        actions = ", ".join(data.get("actions", [])) if isinstance(data, dict) else ""
        ontology_lines.append(
            f"- {entity}: synonyms=[{synonyms}] problems=[{problems}] actions=[{actions}]"
        )

    municipality_lines = []
    for region in (municipalities.get("regions") or [])[:15]:
        if not isinstance(region, dict):
            continue
        municipality_lines.append(
            f"- {region.get('name')}: crops={region.get('crops', [])} problems={region.get('problems', [])}"
        )

    return "\n".join(
        [
            "Cultivos reconocidos por el motor y útiles en el dominio:",
            *crop_lines,
            "",
            "Riesgos agrícolas de referencia:",
            *hazard_lines,
            "",
            "Vocabulario regional para narrativas campesinas:",
            *vocab_terms,
            "",
            "Ontología agrícola local:",
            *ontology_lines,
            "",
            "Municipios / regiones relevantes del Estado de México:",
            *municipality_lines,
        ]
    )


JSON_TEMPLATE = """{
  "goal": {
    "id": "<snake_case>",
    "display_name": "<nombre legible>",
    "description": "<1-2 oraciones>",
    "pyramid_level": "<SURVIVAL|DUTY|OPPORTUNITY|NEED|ATTENTION_CYCLE>",
    "activation_when": "<expresión o condición>",
    "plan_ref": "<id del plan>",
    "contribution_rules": {"fixed_value": 0.5},
    "emotion_tag": "neutral"
  },
  "plan": {
    "id": "<snake_case>",
    "display_name": "<nombre legible>",
    "description": "<1-2 oraciones>",
    "goal_id": "<id del goal>",
    "steps": [
      {
        "id": "step_1",
        "action": "<acción válida>",
        "args": {}
      }
    ]
  }
}"""


def build_system_prompt(candidates_text: str = "") -> str:
    sections = [
        "Eres AgroIntent, un extractor autónomo de metas e intenciones agrícolas en español.",
        "Devuelve SOLO JSON válido. Nada de markdown, nada de explicación, nada de texto extra.",
        "Nunca omitas campos obligatorios.",
        "Si un campo no se puede inferir con seguridad, usa el valor más razonable y consistente.",
        "No inventes acciones fuera del catálogo permitido.",
        "Prefiere metas y planes ya existentes en el corpus recuperado; solo crea uno nuevo si ninguno encaja.",
        "Si el texto usa vocabulario rural del Estado de México, usa ese vocabulario en display_name y description.",
        "",
        "## Reglas duras",
        "1. goal.plan_ref debe apuntar exactamente a plan.id.",
        "2. plan.goal_id debe apuntar exactamente a goal.id.",
        "3. Cada step debe tener id, action y args.",
        "4. step.id debe existir siempre; si falta, usa step_1, step_2, ...",
        "5. display_name y description nunca deben faltar.",
        "6. pyramid_level solo puede ser uno de los 5 valores válidos.",
        "7. Usa args, nunca params.",
        "",
        "## Formato obligatorio",
        JSON_TEMPLATE,
        "",
        "## Catálogo de acciones",
        _render_actions_doc(),
        "",
        "## Señales de dominio",
        _render_domain_hints(),
    ]

    if candidates_text.strip():
        sections.extend(
            [
                "",
                "## Candidatos recuperados desde el corpus",
                candidates_text.strip(),
                "",
                "Si alguno encaja semánticamente, reutiliza su goal_id y plan_id.",
            ]
        )

    fewshot = _safe_read(FEWSHOT_PATH).strip()
    if fewshot:
        sections.extend(["", "## Ejemplos de referencia", fewshot])

    return "\n".join(sections).strip()


SYSTEM_PROMPT = build_system_prompt()


def build_user_prompt(narrative: str, family_alias: str = "generic") -> str:
    return (
        f"Alias del agente o familia: {family_alias}\n\n"
        f"Narrativa:\n{narrative}\n\n"
        "Devuelve el JSON completo siguiendo la plantilla."
    )


def build_repair_prompt(previous_json: str, errors: list[str]) -> str:
    error_text = "\n".join(f"- {e}" for e in errors) if errors else "- Error desconocido"
    return (
        "Corrige el JSON anterior para que cumpla exactamente la plantilla.\n"
        "No agregues texto fuera del JSON.\n"
        "No inventes campos nuevos.\n"
        "Corrige solo lo que falla.\n\n"
        f"Errores detectados:\n{error_text}\n\n"
        f"JSON anterior:\n{previous_json}"
    )