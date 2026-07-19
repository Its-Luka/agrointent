from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml
from pydantic import ValidationError

from schemas import ExtractionResult

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CORPUS = BASE_DIR / "files"

PYRAMID_NORMALIZATION = {
    "SURVIVAL": "SURVIVAL",
    "DUTY": "DUTY",
    "NEED": "NEED",
    "ATTENTION_CYCLE": "ATTENTION_CYCLE",
    "OPORTUNITY": "OPPORTUNITY",
    "REQUIREMENT": "OPPORTUNITY",
    "SOCIAL": "NEED",
}


def load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def discover_roots(corpus_root: Path) -> tuple[Path, Path]:
    goals = corpus_root / "goals"
    plans = corpus_root / "plans"
    if goals.exists() and plans.exists():
        return goals, plans
    goals = corpus_root / "files" / "goals"
    plans = corpus_root / "files" / "plans"
    if goals.exists() and plans.exists():
        return goals, plans
    raise SystemExit("No encontré goals/plans en la ruta indicada.")


def find_plan_path(plans_root: Path, category: str, goal_id: str) -> Path | None:
    candidates = [
        plans_root / category / f"{goal_id}.yaml",
        plans_root / category / f"{goal_id}_plan.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def _humanize(text: str) -> str:
    return text.replace("_", " ").replace("-", " ").strip().title()


def build_narrative(goal: dict) -> str:
    desc = (goal.get("description") or "").strip()
    act = (goal.get("activation_when") or "").strip()
    if act:
        return f"{desc} Esto aplica cuando {act}."
    return desc or "Narrativa sintética generada desde el corpus."


def build_summary(goal: dict, plan: dict) -> str:
    display = goal.get("display_name") or _humanize(goal.get("id", "meta"))
    level = goal.get("pyramid_level") or "NEED"
    act = goal.get("activation_when") or "una condición agrícola o social relevante"
    return (
        f"Meta: {display}. Nivel: {level}. "
        f"Se activa cuando {act}. "
        f"El plan asociado organiza acciones concretas para responder a esa necesidad."
    )


def _step_to_spanish(step: dict) -> str:
    action = str(step.get("action") or "").strip()
    args = step.get("args") or {}

    if action == "agro_ecosystem_operation":
        op = str(args.get("operation") or "").upper()
        crop = str(args.get("crop_type") or "").strip()
        if crop:
            return f"realizar la operación {op.lower()} sobre el cultivo de {crop}"
        return f"realizar la operación agrícola {op.lower()}"

    if action == "set_land_crop_type":
        return f"definir el cultivo {args.get('crop_type', 'indicado')}"

    if action == "consume_resource":
        return f"consumir {args.get('amount', 0)} unidades de {args.get('key', 'recurso')}"

    if action == "increment_belief":
        return f"incrementar {args.get('key', 'creencia')} en {args.get('amount', 0)}"

    if action == "update_belief":
        return f"actualizar {args.get('key', 'creencia')} a {args.get('value', '')}"

    if action == "emit_episode":
        text = str(args.get("text") or "").strip()
        return f"registrar episodio narrativo: {text or 'evento'}"

    if action == "emit_emotion":
        return f"aplicar emoción en {args.get('axis', 'axis')} con delta {args.get('delta', 0)}"

    if action == "send_society_collaboration":
        return "solicitar colaboración a la comunidad"

    if action == "send_marketplace_event":
        return "publicar un evento en el mercado"

    if action == "send_civic_land_request":
        return "solicitar trámite de tierra"

    if action == "conditional":
        return "aplicar una condición dentro del plan"

    return action or "acción no especificada"


def build_explanation(goal: dict, plan: dict) -> str:
    display = goal.get("display_name") or _humanize(goal.get("id", "meta"))
    steps = plan.get("steps", []) or []
    if not steps:
        return f"La meta {display} fue detectada, pero el plan no contiene pasos."

    step_lines = []
    for i, step in enumerate(steps, start=1):
        step_lines.append(f"{i}. {_step_to_spanish(step)}")

    return (
        f"La meta detectada es {display}. "
        f"El plan propone estas acciones:\n" + "\n".join(step_lines)
    )


def build_example(goal_path: Path, plan_path: Path) -> tuple[dict, dict] | None:
    raw_goal = load_yaml(goal_path)
    raw_plan = load_yaml(plan_path)

    goal_id = raw_goal.get("id")
    if not goal_id:
        return None

    raw_level = str(raw_goal.get("pyramid_level", "")).upper()
    level = PYRAMID_NORMALIZATION.get(raw_level)
    if level is None:
        print(f"[SKIP] {goal_id}: pyramid_level desconocido '{raw_level}'")
        return None

    goal = {
        "id": goal_id,
        "display_name": raw_goal.get("display_name") or _humanize(goal_id),
        "description": raw_goal.get("description", ""),
        "pyramid_level": level,
        "activation_when": raw_goal.get("activation_when", ""),
        "plan_ref": raw_goal.get("plan_ref") or raw_plan.get("id"),
        "contribution_rules": {"fixed_value": (raw_goal.get("contribution_rules") or {}).get("fixed_value", 0.5)},
        "emotion_tag": raw_goal.get("emotion_tag", "neutral"),
    }

    steps = []
    for i, s in enumerate(raw_plan.get("steps", []) or [], start=1):
        steps.append(
            {
                "id": s.get("id") or f"step_{i}",
                "action": s.get("action", ""),
                "args": s.get("args", {}) or {},
            }
        )

    if raw_plan.get("on_timeout") or raw_plan.get("on_failure"):
        print(f"[INFO] {goal_id}: se omiten on_timeout/on_failure (schema actual no los modela).")

    plan = {
        "id": raw_plan.get("id") or f"{goal_id}_plan",
        "display_name": raw_plan.get("display_name") or _humanize(raw_plan.get("id", goal_id)),
        "description": raw_plan.get("description", ""),
        "goal_id": goal_id,
        "steps": steps,
    }

    return goal, plan


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus-root", default=str(DEFAULT_CORPUS))
    ap.add_argument("--out-md", default="prompts/fewshot.md")
    ap.add_argument("--out-json", default="prompts/fewshot_examples.json")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    corpus_root = Path(args.corpus_root).resolve()
    goals_root, plans_root = discover_roots(corpus_root)

    examples = []
    scanned = 0
    orphans = []

    for category_dir in sorted(goals_root.iterdir()):
        if not category_dir.is_dir():
            continue
        category = category_dir.name

        for goal_path in sorted(category_dir.glob("*.yaml")):
            scanned += 1
            goal_id = goal_path.stem
            plan_path = find_plan_path(plans_root, category, goal_id)
            if plan_path is None:
                orphans.append(f"{category}/{goal_id}")
                continue

            try:
                built = build_example(goal_path, plan_path)
                if not built:
                    continue
                goal, plan = built
                ExtractionResult(goal=goal, plan=plan).relink()
            except ValidationError as e:
                print(f"[INVALIDO] {category}/{goal_id}: {e}")
                continue
            except Exception as e:
                print(f"[ERROR] {category}/{goal_id}: {e}")
                continue

            examples.append(
                {
                    "narrativa": build_narrative(goal),
                    "resumen": build_summary(goal, plan),
                    "explicacion": build_explanation(goal, plan),
                    "goal": goal,
                    "plan": plan,
                }
            )

    if args.limit:
        examples = examples[: args.limit]

    out_md = Path(args.out_md)
    out_json = Path(args.out_json)
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_json.parent.mkdir(parents=True, exist_ok=True)

    with out_md.open("w", encoding="utf-8") as f:
        f.write("# Ejemplos few-shot generados desde el corpus local\n\n")
        f.write(f"_Válidos: {len(examples)} | Escaneados: {scanned} | Huérfanos: {len(orphans)}_\n\n")
        for i, ex in enumerate(examples, start=1):
            payload = {
                "goal": ex["goal"],
                "plan": ex["plan"],
                "resumen": ex["resumen"],
                "explicacion": ex["explicacion"],
            }
            f.write(f"## Ejemplo {i}\n\n")
            f.write(f"**Narrativa:**\n{ex['narrativa']}\n\n")
            f.write(f"**Resumen:**\n{ex['resumen']}\n\n")
            f.write(f"**Explicación:**\n{ex['explicacion']}\n\n")
            f.write("```json\n")
            f.write(json.dumps(payload, ensure_ascii=False, indent=2))
            f.write("\n```\n\n")

    out_json.write_text(json.dumps(examples, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Escaneados: {scanned}")
    print(f"Huérfanos: {len(orphans)}")
    print(f"Ejemplos válidos: {len(examples)}")
    print(f"Escrito: {out_md}")
    print(f"Escrito: {out_json}")


if __name__ == "__main__":
    main()