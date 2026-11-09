"""Lista de alterações devolvida pelo verificador: leitura e aplicação.

O verificador não reescreve a letra; propõe alterações pontuais sobre os segmentos
numerados do rascunho, e este módulo as aplica. Operações:

- ``replace``: troca ``old`` por ``new`` dentro do segmento ``segment``;
- ``delete``: remove ``old`` do segmento ``segment`` (trecho inventado);
- ``insert``: insere ``new`` depois do segmento ``segment`` (0 = antes do primeiro),
  para trechos que o rascunho pulou.

``old`` precisa aparecer **exatamente uma vez** no segmento, como palavras inteiras.
Alterações que não cumprem as regras são rejeitadas (com o motivo), não aplicadas.
Resposta mal formada levanta ``EditParseError``: nunca vira "nenhuma alteração",
porque isso a confundiria com um empate com o baseline.
"""

import json
import re
from dataclasses import asdict, dataclass

OPS = ("replace", "delete", "insert")


class EditParseError(ValueError):
    """A resposta do verificador não é uma lista de alterações válida."""


@dataclass
class Edit:
    op: str
    segment: int
    old: str = ""
    new: str = ""
    heard: str = ""


@dataclass
class EditOutcome:
    edit: Edit
    applied: bool
    reason: str = ""

    def to_dict(self) -> dict:
        return {**asdict(self.edit), "applied": self.applied, "reason": self.reason}


def _extract_json(raw: str) -> object:
    text = raw.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, flags=re.DOTALL)
    if fence:
        text = fence.group(1)
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end < start:
        raise EditParseError("resposta sem objeto JSON")
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError as e:
        raise EditParseError(f"JSON inválido: {e}") from e


def parse_edits(raw: str) -> list[Edit]:
    data = _extract_json(raw)
    if not isinstance(data, dict) or not isinstance(data.get("edits"), list):
        raise EditParseError('esperado um objeto com a lista "edits"')

    edits = []
    for i, item in enumerate(data["edits"], 1):
        if not isinstance(item, dict):
            raise EditParseError(f"alteração {i} não é um objeto")
        op = item.get("op")
        if op not in OPS:
            raise EditParseError(f"alteração {i}: operação desconhecida {op!r}")
        seg = item.get("segment")
        if isinstance(seg, bool) or not isinstance(seg, int):
            raise EditParseError(f"alteração {i}: 'segment' deve ser inteiro")
        fields = {k: item.get(k, "") for k in ("old", "new", "heard")}
        if not all(isinstance(v, str) for v in fields.values()):
            raise EditParseError(f"alteração {i}: 'old', 'new' e 'heard' devem ser texto")
        if op in ("replace", "delete") and not fields["old"].strip():
            raise EditParseError(f"alteração {i}: '{op}' exige 'old'")
        if op in ("replace", "insert") and not fields["new"].strip():
            raise EditParseError(f"alteração {i}: '{op}' exige 'new'")
        edits.append(Edit(op=op, segment=seg, **fields))
    return edits


def _find_unique(segment_text: str, old: str) -> tuple[int, int] | None | str:
    pattern = re.compile(r"(?<!\w)" + re.escape(old.strip()) + r"(?!\w)")
    matches = list(pattern.finditer(segment_text))
    if not matches:
        return "trecho não encontrado no segmento"
    if len(matches) > 1:
        return "trecho ambíguo (aparece mais de uma vez no segmento)"
    return matches[0].span()


def apply_edits(segments: list[str], edits: list[Edit]) -> tuple[str, list[EditOutcome]]:
    """Aplica as alterações válidas e devolve o texto final e o destino de cada uma."""
    n = len(segments)
    spans: dict[int, list[tuple[int, int, str]]] = {}
    inserts: dict[int, list[str]] = {}
    outcomes: list[EditOutcome] = []

    for edit in edits:
        if edit.op == "insert":
            if not 0 <= edit.segment <= n:
                outcomes.append(EditOutcome(edit, False, "segmento inexistente"))
                continue
            inserts.setdefault(edit.segment, []).append(edit.new.strip())
            outcomes.append(EditOutcome(edit, True))
            continue

        if not 1 <= edit.segment <= n:
            outcomes.append(EditOutcome(edit, False, "segmento inexistente"))
            continue
        if edit.op == "replace" and edit.old.strip() == edit.new.strip():
            outcomes.append(EditOutcome(edit, False, "alteração sem efeito"))
            continue
        found = _find_unique(segments[edit.segment - 1], edit.old)
        if isinstance(found, str):
            outcomes.append(EditOutcome(edit, False, found))
            continue
        start, end = found
        taken = spans.setdefault(edit.segment, [])
        if any(start < e and s < end for s, e, _ in taken):
            outcomes.append(EditOutcome(edit, False, "sobreposta a outra alteração"))
            continue
        taken.append((start, end, edit.new.strip() if edit.op == "replace" else ""))
        outcomes.append(EditOutcome(edit, True))

    parts: list[str] = list(inserts.get(0, []))
    for i, text in enumerate(segments, 1):
        for start, end, new in sorted(spans.get(i, []), reverse=True):
            text = text[:start] + new + text[end:]
        parts.append(text)
        parts.extend(inserts.get(i, []))
    final = re.sub(r"\s+", " ", " ".join(parts)).strip()
    final = re.sub(r"\s+([.,;:!?])", r"\1", final)
    return final, outcomes
