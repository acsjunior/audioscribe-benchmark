"""Registro do custo de cada chamada a API (tokens, duração do áudio, tempo de resposta).

Os provedores devolvem o uso em formatos diferentes; ``usage_record`` reduz todos a um
dicionário comum e guarda o original em ``raw`` (que inclui, quando o provedor informa,
o detalhamento por modalidade: tokens de áudio e de texto têm preços diferentes).

Formatos conhecidos:

- OpenAI Chat Completions: ``prompt_tokens``, ``completion_tokens``, ``total_tokens``;
- OpenAI transcrição (``gpt-4o-transcribe``): ``input_tokens``, ``output_tokens``,
  ``total_tokens``; (``whisper-1``): ``type="duration"`` com ``seconds``;
- Gemini: ``prompt_token_count``, ``candidates_token_count``, ``total_token_count``.
"""

_INPUT_KEYS = ("input_tokens", "prompt_tokens", "prompt_token_count")
_OUTPUT_KEYS = ("output_tokens", "completion_tokens", "candidates_token_count")
_TOTAL_KEYS = ("total_tokens", "total_token_count")


def _dump(raw) -> dict | None:
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    dump = getattr(raw, "model_dump", None)
    if callable(dump):
        try:
            data = dump(mode="json", exclude_none=True)
        except TypeError:
            data = dump()
        if isinstance(data, dict):
            return data
    return None


def _first_number(data: dict, keys: tuple[str, ...]) -> float | int | None:
    for key in keys:
        value = data.get(key)
        if isinstance(value, int | float) and not isinstance(value, bool):
            return value
    return None


def usage_record(raw, response_time_ms: float | None) -> dict:
    """Uso de uma chamada, em formato comum. Campos que o provedor não informa ficam None."""
    data = _dump(raw) or {}
    inp = _first_number(data, _INPUT_KEYS)
    out = _first_number(data, _OUTPUT_KEYS)
    total = _first_number(data, _TOTAL_KEYS)
    if total is None and inp is not None and out is not None:
        total = inp + out
    seconds = data.get("seconds") if data.get("type") == "duration" else None
    return {
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": total,
        "audio_seconds": seconds,
        "response_time_ms": round(response_time_ms) if response_time_ms is not None else None,
        "raw": data or None,
    }


def as_usage(value) -> dict | None:
    """``value`` se for um registro de uso; None caso contrário (ex.: dublês de teste)."""
    return value if isinstance(value, dict) else None
