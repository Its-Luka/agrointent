from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class GoalIndexItem:
    id: str
    display_name: str
    description: str
    pyramid_level: str
    activation_when: str
    plan_ref: str
    category: str
    source_path: str


@dataclass
class PlanIndexItem:
    id: str
    display_name: str
    description: str
    goal_id: str
    num_steps: int
    actions: list[str]
    category: str
    source_path: str


def _strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def _normalize_text(text: str) -> str:
    text = _strip_accents(text or "").lower()
    text = re.sub(r"[^a-z0-9_ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _safe_read_yaml(path: Path) -> dict[str, Any]:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except Exception:
        return {}


def discover_corpus_roots(base_dir: Path) -> tuple[Path, Path]:
    candidates = [
        (base_dir / "files" / "goals", base_dir / "files" / "plans"),
        (base_dir / "data" / "ebdi" / "goals", base_dir / "data" / "ebdi" / "plans"),
    ]

    for goals_root, plans_root in candidates:
        if goals_root.exists() and plans_root.exists():
            return goals_root, plans_root

    raise FileNotFoundError(
        "No encontré el corpus. Debe existir files/goals y files/plans, "
        "o data/ebdi/goals y data/ebdi/plans."
    )


def find_plan_path(plans_root: Path, category: str, goal_id: str) -> Path | None:
    candidates = [
        plans_root / category / f"{goal_id}.yaml",
        plans_root / category / f"{goal_id}_plan.yaml",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def build_goal_index(goals_root: Path, plans_root: Path) -> list[GoalIndexItem]:
    items: list[GoalIndexItem] = []

    for category_dir in sorted(goals_root.iterdir()):
        if not category_dir.is_dir():
            continue

        category = category_dir.name
        for goal_file in sorted(category_dir.glob("*.yaml")):
            goal = _safe_read_yaml(goal_file)
            goal_id = str(goal.get("id") or "").strip()
            if not goal_id:
                continue

            plan_path = find_plan_path(plans_root, category, goal_id)
            if not plan_path:
                continue

            items.append(
                GoalIndexItem(
                    id=goal_id,
                    display_name=str(goal.get("display_name") or goal_id.replace("_", " ").title()),
                    description=str(goal.get("description") or ""),
                    pyramid_level=str(goal.get("pyramid_level") or ""),
                    activation_when=str(goal.get("activation_when") or ""),
                    plan_ref=str(goal.get("plan_ref") or plan_path.stem),
                    category=category,
                    source_path=str(goal_file.as_posix()),
                )
            )

    return items


def build_plan_index(plans_root: Path) -> list[PlanIndexItem]:
    items: list[PlanIndexItem] = []

    for category_dir in sorted(plans_root.iterdir()):
        if not category_dir.is_dir():
            continue

        category = category_dir.name
        for plan_file in sorted(category_dir.glob("*.yaml")):
            plan = _safe_read_yaml(plan_file)
            plan_id = str(plan.get("id") or "").strip()
            if not plan_id:
                continue

            steps = plan.get("steps") or []
            actions: list[str] = []
            if isinstance(steps, list):
                for s in steps:
                    if isinstance(s, dict):
                        action = s.get("action")
                        if action:
                            actions.append(str(action))

            items.append(
                PlanIndexItem(
                    id=plan_id,
                    display_name=str(plan.get("display_name") or plan_id.replace("_", " ").title()),
                    description=str(plan.get("description") or ""),
                    goal_id=str(plan.get("goal_id") or ""),
                    num_steps=len(actions),
                    actions=actions,
                    category=category,
                    source_path=str(plan_file.as_posix()),
                )
            )

    return items


def make_search_blob_goal(item: GoalIndexItem) -> str:
    parts = [
        item.id,
        item.display_name,
        item.description,
        item.pyramid_level,
        item.activation_when,
        item.category,
    ]
    return _normalize_text(" ".join(parts))


def make_search_blob_plan(item: PlanIndexItem) -> str:
    parts = [
        item.id,
        item.display_name,
        item.description,
        item.goal_id,
        item.category,
        " ".join(item.actions),
    ]
    return _normalize_text(" ".join(parts))


def main() -> None:
    parser = argparse.ArgumentParser(description="Construye índices JSON del corpus local de AgroIntent.")
    parser.add_argument(
        "--base-dir",
        default=".",
        help="Raíz del proyecto. Debe contener files/ o data/ebdi/.",
    )
    parser.add_argument(
        "--out-dir",
        default="knowledge",
        help="Carpeta de salida para los índices.",
    )
    args = parser.parse_args()

    base_dir = Path(args.base_dir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    goals_root, plans_root = discover_corpus_roots(base_dir)

    goal_items = build_goal_index(goals_root, plans_root)
    plan_items = build_plan_index(plans_root)

    goals_json = []
    for item in goal_items:
        d = asdict(item)
        d["search_blob"] = make_search_blob_goal(item)
        goals_json.append(d)

    plans_json = []
    for item in plan_items:
        d = asdict(item)
        d["search_blob"] = make_search_blob_plan(item)
        plans_json.append(d)

    goal_index_path = out_dir / "goal_index.json"
    plan_index_path = out_dir / "plan_index.json"

    goal_index_path.write_text(
        json.dumps(goals_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    plan_index_path.write_text(
        json.dumps(plans_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Goals indexados: {len(goals_json)}")
    print(f"Plans indexados: {len(plans_json)}")
    print(f"Escrito: {goal_index_path}")
    print(f"Escrito: {plan_index_path}")


if __name__ == "__main__":
    main()