import pytest

from benchmark.verification.edits import Edit, EditParseError, apply_edits, parse_edits
from benchmark.verification.segments import MAX_WORDS, render, segment

# --- segmentação ---

def test_segment_cuts_at_punctuation_after_min_words():
    text = "um dois três quatro cinco seis sete oito, nove dez onze doze treze quatorze quinze."
    assert segment(text) == [
        "um dois três quatro cinco seis sete oito,",
        "nove dez onze doze treze quatorze quinze.",
    ]


def test_segment_forces_cut_at_max_words():
    words = [f"w{i}" for i in range(40)]
    segs = segment(" ".join(words))
    assert all(len(s.split()) <= MAX_WORDS for s in segs[:-1])
    assert " ".join(segs).split() == words


def test_segment_merges_short_tail_and_respects_lines():
    assert segment("a b c d e f g h i.\nj") == ["a b c d e f g h i. j"]
    assert segment("") == []


def test_render_numbers_segments():
    assert render(["a b", "c"]) == "[1] a b\n[2] c"


# --- leitura ---

def test_parse_accepts_fenced_json_and_empty_list():
    assert parse_edits('```json\n{"edits": []}\n```') == []
    edits = parse_edits(
        'Segue: {"edits": [{"op": "replace", "segment": 2, "old": "a", "new": "b"}]}'
    )
    assert edits == [Edit(op="replace", segment=2, old="a", new="b")]


@pytest.mark.parametrize(
    "raw",
    [
        "não há alterações",
        '{"edit": []}',
        '{"edits": [{"op": "rewrite", "segment": 1}]}',
        '{"edits": [{"op": "replace", "segment": "1", "old": "a", "new": "b"}]}',
        '{"edits": [{"op": "replace", "segment": 1, "old": "", "new": "b"}]}',
        '{"edits": [{"op": "insert", "segment": 1}]}',
        '{"edits": [',
    ],
)
def test_parse_rejects_malformed(raw):
    with pytest.raises(EditParseError):
        parse_edits(raw)


# --- aplicação ---

SEGS = ["ele está dançando na porta-bamba,", "toca cuíca, toca sulto e tamborim"]


def test_apply_replace_delete_insert():
    edits = [
        Edit("replace", 1, "porta-bamba", "corda bamba"),
        Edit("replace", 2, "sulto", "surdo"),
        Edit("insert", 0, new="Oh Antonico"),
        Edit("delete", 2, "toca cuíca,"),
    ]
    text, outcomes = apply_edits(SEGS, edits)
    assert all(o.applied for o in outcomes)
    assert text == "Oh Antonico ele está dançando na corda bamba, toca surdo e tamborim"


@pytest.mark.parametrize(
    ("edit", "reason"),
    [
        (Edit("replace", 3, "a", "b"), "inexistente"),
        (Edit("replace", 1, "samba", "x"), "não encontrado"),
        (Edit("replace", 2, "toca", "x"), "ambíguo"),
        (Edit("replace", 1, "na", "na"), "sem efeito"),
        (Edit("insert", 5, new="x"), "inexistente"),
        (Edit("replace", 1, "dança", "x"), "não encontrado"),  # só palavra inteira
    ],
)
def test_apply_rejects_invalid(edit, reason):
    text, (outcome,) = apply_edits(SEGS, [edit])
    assert not outcome.applied
    assert reason in outcome.reason
    assert text == " ".join(SEGS)


def test_apply_rejects_overlap_keeps_first():
    edits = [Edit("replace", 2, "sulto e", "surdo e"), Edit("replace", 2, "e tamborim", "x")]
    text, outcomes = apply_edits(SEGS, edits)
    assert [o.applied for o in outcomes] == [True, False]
    assert "surdo e tamborim" in text
