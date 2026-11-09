import pytest

from benchmark.consensus import edit_distance, medoid


def test_edit_distance_normalizes_and_counts_words():
    assert edit_distance("A rosa, não fala!", "a rosa nao fala") == 1
    assert edit_distance("a b c", "a b c") == 0
    assert edit_distance("", "a b") == 2
    assert edit_distance("a b", "") == 2


def test_medoid_picks_most_central():
    texts = {
        1: "as rosas nao falam",
        2: "as rosas nao falam",
        3: "totalmente outra coisa aqui agora",
    }
    assert medoid(texts) in (1, 2)


def test_medoid_discards_outlier_in_the_middle():
    texts = {1: "a b c d", 2: "a b c x", 3: "a b c d e f g h"}
    # 1 está a 1 de 2 e a 4 de 3 (soma 5); 2: 1+5=6; 3: 4+5=9
    assert medoid(texts) == 1


def test_medoid_tie_breaks_by_lowest_run():
    assert medoid({3: "a b", 1: "a b", 2: "a b"}) == 1


def test_medoid_needs_three_runs():
    with pytest.raises(ValueError, match="ao menos 3"):
        medoid({1: "a", 2: "b"})
