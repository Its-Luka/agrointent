from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

import streamlit as st
import yaml
from dotenv import load_dotenv

load_dotenv()

from context_summarizer import summarize_uploaded_context  # noqa: E402
from extractor import extract_intent  # noqa: E402

OUTPUTS_DIR = Path(os.getenv("OUTPUTS_DIR", "outputs"))
OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)

st.set_page_config(page_title="AgroIntent", layout="wide")
st.title("🌾 AgroIntent")

st.caption(
    "Escribe una narrativa, sube un archivo `.md` o `.txt`, o usa ambos. "
    "La app resumirá el contexto y extraerá la intención agrícola en una sola pantalla."
)


ACTION_HUMAN = {
    "agro_ecosystem_operation": "operación agrícola",
    "set_land_crop_type": "definir cultivo",
    "consume_resource": "consumir recurso",
    "increment_belief": "ajustar creencia",
    "update_belief": "actualizar creencia",
    "increase_health": "mejorar salud",
    "emit_episode": "registrar episodio",
    "emit_emotion": "registrar emoción",
    "send_society_collaboration": "pedir colaboración comunitaria",
    "spend_friends_time": "pasar tiempo con amistades",
    "send_marketplace_event": "publicar evento de mercado",
    "send_civic_land_request": "solicitar trámite de tierra",
    "send_event": "emitir evento",
    "sync_clock": "sincronizar reloj",
    "log_audit": "registrar auditoría",
    "wait_for_event": "esperar evento",
    "conditional": "ramificar condición",
}


OPERATION_HUMAN = {
    "PREPARE": "preparar la tierra",
    "PLANT": "sembrar",
    "CHECK": "revisar el cultivo",
    "IRRIGATE": "regar",
    "PESTICIDE": "fumigar",
    "HARVEST": "cosechar",
    "DEFOREST": "desmontar terreno",
    "SELL": "vender la cosecha",
}


RESOURCE_HUMAN = {
    "money": "dinero",
    "time_left_on_day": "tiempo disponible del día",
    "seeds": "semillas",
    "water_available": "agua disponible",
    "tools": "herramientas",
}


BELIEF_HUMAN = {
    "money": "dinero",
    "health": "salud",
    "happiness": "bienestar emocional",
    "food_security": "seguridad alimentaria",
    "social_capital": "apoyo social",
    "days_in_crisis": "días en crisis",
    "harvested_weight": "peso cosechado",
    "total_harvested_weight": "peso total cosechado",
    "tools": "herramientas",
    "seeds": "semillas",
    "water_available": "agua disponible",
    "time_left_on_day": "tiempo del día",
    "last_crop_type": "último cultivo",
    "resource_needed_type": "tipo de recurso necesario",
    "current_day": "día actual",
    "price_list_available": "lista de precios disponible",
}


def _safe_filename(name: str) -> str:
    name = name.strip().lower()
    name = re.sub(r"[^a-z0-9_\-]+", "_", name)
    return name[:80] or "agrointent"


def _read_uploaded_file(uploaded_file) -> str:
    if uploaded_file is None:
        return ""
    raw_bytes = uploaded_file.getvalue()
    return raw_bytes.decode("utf-8", errors="ignore")


def _combine_texts(*parts: str) -> str:
    cleaned = [p.strip() for p in parts if p and p.strip()]
    return "\n\n".join(cleaned).strip()


def _describe_step(step) -> str:
    action = step.action
    args = step.args or {}

    if action == "agro_ecosystem_operation":
        op = str(args.get("operation", "")).upper()
        crop = str(args.get("crop_type", "")).strip()
        op_text = OPERATION_HUMAN.get(op, op.lower() or "hacer una operación agrícola")
        if crop:
            return f"{op_text} el cultivo de {crop}"
        return op_text

    if action == "consume_resource":
        key = str(args.get("key", "")).strip()
        amount = args.get("amount", "")
        resource = RESOURCE_HUMAN.get(key, key)
        return f"usar {amount} unidades de {resource}"

    if action == "increment_belief":
        key = str(args.get("key", "")).strip()
        amount = args.get("amount", "")
        belief = BELIEF_HUMAN.get(key, key)
        return f"ajustar {belief} en {amount}"

    if action == "update_belief":
        key = str(args.get("key", "")).strip()
        value = args.get("value", "")
        belief = BELIEF_HUMAN.get(key, key)
        return f"actualizar {belief} a {value}"

    if action == "emit_episode":
        text = str(args.get("text", "")).strip()
        return f"registrar el episodio: {text or 'evento narrativo'}"

    if action == "emit_emotion":
        axis = str(args.get("axis", "")).strip()
        delta = args.get("delta", "")
        return f"registrar emoción en {axis} con cambio {delta}"

    if action == "send_society_collaboration":
        return "pedir colaboración a la comunidad"

    if action == "send_marketplace_event":
        return "publicar evento de mercado"

    if action == "send_civic_land_request":
        return "solicitar trámite de tierras"

    if action == "spend_friends_time":
        return "pasar tiempo con amistades"

    if action == "conditional":
        return "aplicar una condición dentro del plan"

    return ACTION_HUMAN.get(action, action)


def _plain_spanish_summary(result) -> str:
    if not result.plan.steps:
        return f"Meta probable: {result.goal.display_name}. El plan no trae pasos."

    step_texts = [f"{i+1}) {_describe_step(step)}" for i, step in enumerate(result.plan.steps)]
    return (
        f"Meta probable: {result.goal.display_name}. "
        f"Plan sugerido: " + "; ".join(step_texts) + "."
    )


def _confidence_from_meta(meta) -> int:
    if not getattr(meta, "top_candidates", None):
        base = 55
    else:
        top = meta.top_candidates[0]
        score = float(top.get("score", 0.0) or 0.0)
        base = 45 + int(score * 40)

    if getattr(meta, "repaired", False):
        base -= 5
    if getattr(meta, "retried", False):
        base -= 5

    return max(35, min(95, base))


def _recommendations(result) -> list[str]:
    recs = []
    goal_text = f"{result.goal.id} {result.goal.display_name} {result.goal.description}".lower()

    if any(x in goal_text for x in ("agua", "irrig", "riego", "pipa", "cisterna", "pozo")):
        recs.append("Priorizar el abastecimiento y almacenamiento de agua.")
    if any(x in goal_text for x in ("plaga", "gusano", "barrenador", "fumig")):
        recs.append("Gestionar control zoosanitario o fitosanitario.")
    if any(x in goal_text for x in ("credito", "crédito", "apoyo", "seguro", "financ")):
        recs.append("Solicitar apoyo, crédito o seguro agrícola.")
    if any(x in goal_text for x in ("mercado", "precio", "vender", "coyote")):
        recs.append("Buscar mejor precio o canal de venta.")
    if not recs:
        recs.append("Seguir el plan propuesto paso a paso.")
    return recs


def _plan_explained(result) -> str:
    if not result.plan.steps:
        return "El plan no contiene pasos."
    lines = []
    for i, step in enumerate(result.plan.steps, start=1):
        lines.append(f"{i}. {_describe_step(step)}")
    return "\n".join(lines)


def _summary_payload(summary) -> dict[str, Any]:
    return {
        "file_name": getattr(summary, "file_name", ""),
        "title": getattr(summary, "title", ""),
        "summary": getattr(summary, "summary", ""),
        "key_points": list(getattr(summary, "key_points", []) or []),
        "pending_items": list(getattr(summary, "pending_items", []) or []),
        "keywords": list(getattr(summary, "keywords", []) or []),
        "problems_detected": list(getattr(summary, "problems_detected", []) or []),
        "objectives_possible": list(getattr(summary, "objectives_possible", []) or []),
        "actions_suggested": list(getattr(summary, "actions_suggested", []) or []),
        "risks": list(getattr(summary, "risks", []) or []),
        "crops": list(getattr(summary, "crops", []) or []),
        "resources": list(getattr(summary, "resources", []) or []),
        "mode": getattr(summary, "mode", "heuristic"),
    }


with st.sidebar:
    st.header("Configuración")
    family_alias = st.text_input("Alias del agente/familia", value="generic")
    retries = st.slider("Reintentos", min_value=0, max_value=3, value=1)
    use_combined_context = st.checkbox(
        "Usar también el archivo cargado como contexto para la extracción",
        value=True,
    )

st.subheader("Entrada única")
typed_text = st.text_area(
    "Escribe tu narrativa o pega el contexto del documento",
    placeholder="La sequía de tres semanas dañó el cultivo de maíz de la familia...",
    height=180,
    key="narrative_input",
)

uploaded = st.file_uploader(
    "O arrastra/sube un archivo .md o .txt",
    type=["md", "txt"],
    accept_multiple_files=False,
    key="context_uploader",
)

uploaded_text = _read_uploaded_file(uploaded)
has_text = bool(typed_text and typed_text.strip())
has_file = bool(uploaded and uploaded_text.strip())

if uploaded is not None:
    st.caption(f"Archivo cargado: {uploaded.name}")

    with st.expander("Vista previa del archivo"):
        st.text_area(
            "Contenido del archivo",
            value=uploaded_text[:20000],
            height=260,
            key="context_preview",
        )

analyze_btn = st.button("Analizar", type="primary")

if analyze_btn:
    if not has_text and not has_file:
        st.warning("Escribe texto o carga un archivo antes de analizar.")
        st.stop()

    narrative_text = typed_text.strip() if has_text else ""
    context_text = uploaded_text.strip() if has_file else ""

    if has_text and has_file and use_combined_context:
        analysis_text = _combine_texts(
            "### Narrativa escrita",
            narrative_text,
            "### Contexto del archivo",
            context_text,
        )
        summary_input = analysis_text
        extraction_input = analysis_text
        source_name = uploaded.name if uploaded is not None else "contexto.txt"
    elif has_file and not has_text:
        analysis_text = context_text
        summary_input = analysis_text
        extraction_input = analysis_text
        source_name = uploaded.name if uploaded is not None else "contexto.txt"
    else:
        analysis_text = narrative_text
        summary_input = analysis_text
        extraction_input = analysis_text
        source_name = "narrativa_manual.txt"

    if not analysis_text.strip():
        st.warning("El contenido quedó vacío después de procesarlo.")
        st.stop()

    summary = None
    result = None
    meta = None

    with st.spinner("Resumiendo contexto y extrayendo intención..."):
        try:
            summary = summarize_uploaded_context(source_name, summary_input)
        except Exception as e:
            st.error(f"No se pudo resumir el contexto: {e}")
            st.stop()

        try:
            result, meta = extract_intent(
                extraction_input,
                family_alias=family_alias,
                retries=retries,
                return_meta=True,
            )
        except Exception as e:
            st.error(f"No se pudo extraer la intención: {e}")
            st.stop()

    st.success(f"Goal: `{result.goal.id}` | Plan: `{result.plan.id}`")

    st.caption(
        f"Intentos: {meta.attempts} | Reparado: {'sí' if meta.repaired else 'no'} | "
        f"Reintentado: {'sí' if meta.retried else 'no'}"
    )

    st.subheader("Interpretación para usuario")
    st.info(_plain_spanish_summary(result))

    st.subheader("Plan explicado")
    st.write(_plan_explained(result))

    st.subheader("Recomendaciones")
    for rec in _recommendations(result):
        st.write(f"- {rec}")

    st.metric("Confianza estimada", f"{_confidence_from_meta(meta)}%")

    if getattr(meta, "top_candidates", None):
        with st.expander("Candidatos recuperados desde el corpus"):
            st.json(meta.top_candidates)

    left, right = st.columns(2)
    left.subheader("Goal")
    left.code(result.goal.model_dump_json(indent=2), language="json")
    right.subheader("Plan")
    right.code(result.plan.model_dump_json(indent=2), language="json")

    combined_yaml = yaml.safe_dump(
        result.model_dump(),
        allow_unicode=True,
        sort_keys=False,
    )

    st.subheader("YAML final")
    st.code(combined_yaml, language="yaml")

    out_yaml_path = OUTPUTS_DIR / f"{_safe_filename(result.goal.id)}.yaml"
    out_yaml_path.write_text(combined_yaml, encoding="utf-8")
    st.info(f"YAML guardado en: {out_yaml_path}")

    st.download_button(
        "Descargar YAML",
        data=combined_yaml.encode("utf-8"),
        file_name=f"{_safe_filename(result.goal.id)}.yaml",
        mime="text/yaml",
    )

    st.divider()

    st.subheader("Resumen del contexto")
    st.write(getattr(summary, "title", "Contexto"))

    st.write(getattr(summary, "summary", ""))

    summary_sections = [
        ("Puntos clave", getattr(summary, "key_points", [])),
        ("Pendientes / señales de trabajo", getattr(summary, "pending_items", [])),
        ("Problemas detectados", getattr(summary, "problems_detected", [])),
        ("Objetivos posibles", getattr(summary, "objectives_possible", [])),
        ("Acciones sugeridas", getattr(summary, "actions_suggested", [])),
        ("Riesgos", getattr(summary, "risks", [])),
        ("Cultivos", getattr(summary, "crops", [])),
        ("Recursos", getattr(summary, "resources", [])),
    ]

    for label, items in summary_sections:
        st.subheader(label)
        if items:
            for item in items:
                st.write(f"- {item}")
        else:
            st.write("No se detectaron datos claros.")

    summary_json = _summary_payload(summary)

    st.download_button(
        "Descargar resumen JSON",
        data=json.dumps(summary_json, ensure_ascii=False, indent=2).encode("utf-8"),
        file_name=f"{_safe_filename(source_name)}_summary.json",
        mime="application/json",
    )

    if hasattr(summary, "to_markdown"):
        summary_md = summary.to_markdown()
    else:
        summary_md = (
            f"# {getattr(summary, 'title', 'Resumen')}\n\n"
            f"**Archivo:** {getattr(summary, 'file_name', source_name)}\n\n"
            f"## Resumen\n{getattr(summary, 'summary', '')}\n"
        )

    st.download_button(
        "Descargar resumen Markdown",
        data=summary_md.encode("utf-8"),
        file_name=f"{_safe_filename(source_name)}_summary.md",
        mime="text/markdown",
    )