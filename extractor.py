from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from typing import Any

from dotenv import load_dotenv
from pydantic import ValidationError

from prompt import build_repair_prompt, build_system_prompt, build_user_prompt
from retrieval import load_corpus_index, rank_candidates, render_candidates
from schemas import ExtractionResult, RawExtraction, repair

load_dotenv()

_client = None
_CORPUS = load_corpus_index("files", "knowledge")


@dataclass
class ExtractionMeta:
    attempts: int = 0
    repaired: bool = False
    retried: bool = False
    raw_json: str = ""
    last_error: str = ""
    top_candidates: list[dict[str, Any]] = field(default_factory=list)


def _get_client():
    global _client
    if _client is not None:
        return _client

    try:
        from groq import Groq
    except ModuleNotFoundError as e:
        raise RuntimeError(
            "Falta instalar el paquete 'groq'. Ejecuta: python -m pip install -r requirements.txt"
        ) from e

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("Falta GROQ_API_KEY en el archivo .env")

    _client = Groq(api_key=api_key)
    return _client


def _model_name() -> str:
    return os.getenv("AGROINTENT_MODEL", "llama-3.3-70b-versatile")


def _format_errors(e: ValidationError) -> list[str]:
    out: list[str] = []
    for err in e.errors():
        loc = ".".join(str(p) for p in err["loc"])
        if err["type"] == "missing":
            out.append(f"Falta el campo obligatorio '{loc}'.")
        elif err["type"] == "extra_forbidden":
            out.append(f"Sobra el campo '{loc}', elimínalo por completo.")
        else:
            out.append(f"Campo '{loc}': {err['msg']}.")
    return out


def _call_groq(messages: list[dict]) -> str:
    client = _get_client()
    response = client.chat.completions.create(
        model=_model_name(),
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=messages,
    )
    return response.choices[0].message.content or ""


def _parse_json_object(text: str) -> dict[str, Any]:
    try:
        obj = json.loads(text)
        if not isinstance(obj, dict):
            raise ValueError("La respuesta JSON no es un objeto.")
        return obj
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise ValueError("No se pudo extraer un objeto JSON de la respuesta.")
        obj = json.loads(m.group(0))
        if not isinstance(obj, dict):
            raise ValueError("La respuesta JSON recuperada no es un objeto.")
        return obj


def extract_intent(
    narrative: str,
    family_alias: str = "generic",
    retries: int = 1,
    return_meta: bool = False,
) -> ExtractionResult | tuple[ExtractionResult, ExtractionMeta]:
    if retries < 0:
        raise ValueError("retries no puede ser negativo.")

    ranked = rank_candidates(narrative, _CORPUS, top_k=5)
    candidate_text = render_candidates(ranked)

    meta = ExtractionMeta(
        top_candidates=[
            {
                "goal_id": c.goal_id,
                "plan_id": c.plan_id,
                "display_name": c.display_name,
                "category": c.category,
                "score": c.score,
            }
            for c in ranked
        ]
    )

    system_prompt = build_system_prompt(candidates_text=candidate_text)
    base_messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": build_user_prompt(narrative, family_alias)},
    ]

    last_raw_text = ""
    last_errors: list[str] = []

    for attempt in range(retries + 1):
        meta.attempts = attempt + 1

        if attempt == 0:
            messages = base_messages
        else:
            meta.retried = True
            messages = list(base_messages)
            messages.append({"role": "assistant", "content": last_raw_text})
            messages.append({"role": "user", "content": build_repair_prompt(last_raw_text, last_errors)})

        raw_text = _call_groq(messages)
        last_raw_text = raw_text
        meta.raw_json = raw_text

        try:
            raw_dict = _parse_json_object(raw_text)
        except Exception as parse_error:
            last_errors = [str(parse_error)]
            meta.last_error = str(parse_error)
            if attempt == retries:
                raise ValueError(
                    "La respuesta del modelo no pudo parsearse como JSON.\n"
                    f"Último error: {last_errors[0]}\n"
                    f"Última respuesta: {raw_text}"
                ) from parse_error
            continue

        try:
            repaired_dict = repair(RawExtraction(**raw_dict))
            meta.repaired = repaired_dict != raw_dict
            result = ExtractionResult(**repaired_dict).relink()
            return (result, meta) if return_meta else result
        except ValidationError as ve:
            last_errors = _format_errors(ve)
            meta.last_error = " | ".join(last_errors)
            if attempt == retries:
                raise ValueError(
                    "El modelo no produjo una extracción válida tras agotar reintentos.\n"
                    f"Errores: {last_errors}\n"
                    f"Última respuesta cruda: {raw_text}"
                ) from ve

    raise RuntimeError("Estado inesperado en extract_intent().")