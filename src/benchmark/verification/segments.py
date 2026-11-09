"""Divisão determinística do rascunho em segmentos numerados.

Os rascunhos dos modelos de transcrição costumam vir num parágrafo único, sem quebras
de linha, e o refrão se repete. Para que uma alteração aponte um lugar sem ambiguidade,
o rascunho é dividido em segmentos curtos e numerados, e cada alteração indica o
segmento. A divisão é feita por código, nunca pelo modelo, para ser reproduzível.

Regra: corta no fim de uma linha ou depois de pontuação (``. , ; : ! ?``) quando o
segmento já tem ``MIN_WORDS`` palavras; corta à força em ``MAX_WORDS``. Um último
segmento muito curto é juntado ao anterior.
"""

MIN_WORDS = 8
MAX_WORDS = 15
_BOUNDARY_CHARS = ".,;:!?"


def segment(text: str) -> list[str]:
    tokens: list[tuple[str, bool]] = []
    for line in text.splitlines():
        words = line.split()
        for i, word in enumerate(words):
            boundary = i == len(words) - 1 or word[-1] in _BOUNDARY_CHARS
            tokens.append((word, boundary))

    segments: list[list[str]] = []
    current: list[str] = []
    for word, boundary in tokens:
        current.append(word)
        if (boundary and len(current) >= MIN_WORDS) or len(current) >= MAX_WORDS:
            segments.append(current)
            current = []
    if current:
        if segments and len(current) < MIN_WORDS // 2:
            segments[-1].extend(current)
        else:
            segments.append(current)
    return [" ".join(s) for s in segments]


def render(segments: list[str]) -> str:
    """Texto numerado enviado ao modelo: ``[1] ...`` uma linha por segmento."""
    return "\n".join(f"[{i}] {s}" for i, s in enumerate(segments, 1))
