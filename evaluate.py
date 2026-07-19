from __future__ import annotations

import argparse
import csv
import json
import time
from collections import Counter
from pathlib import Path

import yaml
from dotenv import load_dotenv

load_dotenv()

from extractor import extract_intent  # noqa: E402


def resolve_narratives_path(path_str: str) -> Path:
    p = Path(path_str)
    if p.exists():
        return p
    alt = Path("test") / p.name if p.parent.name == "tests" else Path("tests") / p.name
    if alt.exists():
        return alt
    legacy = Path("test") / "test_narratives.txt"
    if legacy.exists():
        return legacy
    raise FileNotFoundError(f"No encontré el archivo de narrativas: {path_str}")


def load_narratives(path: Path) -> list[str]:
    out = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            out.append(line)
    return out


def load_safe_crop_types(resources_dir: Path) -> set[str]:
    crops_path = resources_dir / "crops.yaml"
    if not crops_path.exists():
        return set()
    data = yaml.safe_load(crops_path.read_text(encoding="utf-8")) or {}
    safe = set()
    for _, synonyms in (data.get("engine_recognized") or {}).items():
        for s in synonyms:
            safe.add(str(s).lower())
    return safe


def crop_fallback_risk(steps, safe_crop_types: set[str]) -> list[str]:
    risky = []
    for s in steps:
        crop = s.args.get("crop_type")
        if crop and str(crop).lower() not in safe_crop_types:
            risky.append(str(crop))
    return risky


def heuristic_goal_match(narrative: str, goal_id: str) -> bool:
    text = narrative.lower()
    tokens = [t for t in goal_id.lower().split("_") if t]
    return all(t in text for t in tokens) if tokens else False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--narratives", default="tests/test_narratives.txt")
    ap.add_argument("--report", default="outputs/report.csv")
    ap.add_argument("--metrics", default="outputs/metrics.json")
    ap.add_argument("--resources", default="resources")
    ap.add_argument("--retries", type=int, default=1)
    ap.add_argument("--family-alias", default="generic")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    narratives_path = resolve_narratives_path(args.narratives)
    narratives = load_narratives(narratives_path)
    if args.limit:
        narratives = narratives[: args.limit]

    safe_crop_types = load_safe_crop_types(Path(args.resources))
    report_path = Path(args.report)
    metrics_path = Path(args.metrics)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_path.parent.mkdir(parents=True, exist_ok=True)

    rows = []
    pyramid_counter = Counter()
    successes = 0
    total_latency = 0.0
    fallback_risk_narratives = 0
    retries_used = 0
    repairs_used = 0
    goal_matches = 0

    for idx, narrative in enumerate(narratives, start=1):
        t0 = time.monotonic()
        row = {
            "idx": idx,
            "narrativa": narrative[:120],
            "exito": False,
            "latencia_s": None,
            "goal_id": "",
            "pyramid_level": "",
            "num_steps": 0,
            "crop_types_riesgosos": "",
            "reparado": False,
            "reintentado": False,
            "goal_match_heuristico": False,
            "error": "",
        }

        try:
            result, meta = extract_intent(
                narrative,
                family_alias=args.family_alias,
                retries=args.retries,
                return_meta=True,
            )
            latency = time.monotonic() - t0

            successes += 1
            total_latency += latency
            pyramid_counter[result.goal.pyramid_level] += 1
            retries_used += 1 if meta.retried else 0
            repairs_used += 1 if meta.repaired else 0

            risky = crop_fallback_risk(result.plan.steps, safe_crop_types)
            if risky:
                fallback_risk_narratives += 1

            goal_ok = heuristic_goal_match(narrative, result.goal.id)
            goal_matches += 1 if goal_ok else 0

            row.update(
                {
                    "exito": True,
                    "latencia_s": round(latency, 2),
                    "goal_id": result.goal.id,
                    "pyramid_level": result.goal.pyramid_level,
                    "num_steps": len(result.plan.steps),
                    "crop_types_riesgosos": ", ".join(risky),
                    "reparado": meta.repaired,
                    "reintentado": meta.retried,
                    "goal_match_heuristico": goal_ok,
                }
            )

            print(
                f"[{idx}] OK  goal={result.goal.id!r:30} pyramid={result.goal.pyramid_level:12} "
                f"steps={len(result.plan.steps)} crop_risk={risky or '-'}"
            )

        except Exception as e:
            latency = time.monotonic() - t0
            total_latency += latency
            row.update({"latencia_s": round(latency, 2), "error": str(e)})
            print(f"[{idx}] FAIL {narrative[:70]!r} -> {e}")

        rows.append(row)

    with report_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
        writer.writeheader()
        writer.writerows(rows)

    total = len(narratives)
    metrics = {
        "narratives": total,
        "successes": successes,
        "success_rate": round(successes / total, 4) if total else 0.0,
        "avg_latency_s": round(total_latency / total, 4) if total else 0.0,
        "pyramid_distribution": dict(pyramid_counter),
        "fallback_risk_narratives": fallback_risk_narratives,
        "repair_rate": round(repairs_used / total, 4) if total else 0.0,
        "retry_rate": round(retries_used / total, 4) if total else 0.0,
        "goal_match_heuristic_rate": round(goal_matches / total, 4) if total else 0.0,
    }

    metrics_path.write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\n--- Resumen ---")
    print(f"Narrativas evaluadas: {total}")
    print(f"Éxitos: {successes}/{total} ({metrics['success_rate']*100:.0f}%)")
    print(f"Latencia promedio: {metrics['avg_latency_s']:.2f}s")
    print(f"Distribución pyramid_level: {dict(pyramid_counter)}")
    print(f"Narrativas con crop_type riesgoso: {fallback_risk_narratives}/{successes if successes else 0}")
    print(f"Repair rate: {metrics['repair_rate']*100:.1f}%")
    print(f"Retry rate: {metrics['retry_rate']*100:.1f}%")
    print(f"Goal-match heurístico: {metrics['goal_match_heuristic_rate']*100:.1f}%")
    print(f"Reporte: {report_path}")
    print(f"Métricas: {metrics_path}")


if __name__ == "__main__":
    main()