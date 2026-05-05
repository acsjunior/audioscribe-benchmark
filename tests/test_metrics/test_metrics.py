import pytest
from unittest.mock import MagicMock, patch

from benchmark.metrics import get_metrics
from benchmark.metrics.base import normalize
from benchmark.metrics.bertscore import BERTScoreMetric
from benchmark.metrics.cer import CERMetric
from benchmark.metrics.wer import WERMetric


def test_wer_perfect_match():
    assert WERMetric().compute("as rosas não falam", "as rosas não falam") == 0.0


def test_wer_all_wrong():
    result = WERMetric().compute("adeus terra", "as rosas não falam")
    assert result > 0.0


def test_wer_one_word_wrong():
    result = WERMetric().compute("as rosas não cantam", "as rosas não falam")
    assert 0.0 < result <= 1.0


def test_cer_perfect_match():
    assert CERMetric().compute("as rosas", "as rosas") == 0.0


def test_cer_partial_error():
    result = CERMetric().compute("as rozas", "as rosas")
    assert 0.0 < result <= 1.0


@patch("benchmark.metrics.bertscore.bert_score_fn")
def test_bertscore_compute(mock_fn):
    mock_f1 = MagicMock()
    mock_f1.item.return_value = 0.95
    mock_fn.return_value = (MagicMock(), MagicMock(), mock_f1)

    result = BERTScoreMetric().compute("as rosas não falam", "as rosas não falam")

    assert result == 0.95
    mock_fn.assert_called_once_with(
        ["as rosas não falam"], ["as rosas não falam"], lang="pt", verbose=False
    )


def test_get_metrics_returns_correct_instances():
    metrics = get_metrics(["wer", "cer"])
    assert len(metrics) == 2
    assert metrics[0].name == "wer"
    assert metrics[1].name == "cer"


def test_get_metrics_unknown_raises():
    with pytest.raises(ValueError, match="Unknown metric"):
        get_metrics(["metrica_inexistente"])


# --- normalize ---

def test_normalize_lowercase():
    assert normalize("As Rosas Não Falam") == "as rosas não falam"


def test_normalize_removes_punctuation():
    assert normalize("as rosas não falam,") == "as rosas não falam"


def test_normalize_keeps_accents():
    assert normalize("não") == "não"


def test_normalize_collapses_newlines():
    assert normalize("não falam\napenas perfumam") == "não falam apenas perfumam"


def test_normalize_collapses_multiple_spaces():
    assert normalize("as  rosas") == "as rosas"


# --- WER com normalização ---

def test_wer_ignores_punctuation():
    assert WERMetric().compute("as rosas não falam,", "as rosas não falam") == 0.0


def test_wer_ignores_capitalization():
    assert WERMetric().compute("As Rosas Não Falam", "as rosas não falam") == 0.0


def test_wer_ignores_newlines():
    assert WERMetric().compute("não falam\napenas perfumam", "não falam apenas perfumam") == 0.0


def test_wer_penalizes_accent_difference():
    result = WERMetric().compute("nao falam", "não falam")
    assert result > 0.0


# --- CER com normalização ---

def test_cer_ignores_punctuation():
    assert CERMetric().compute("as rosas não falam,", "as rosas não falam") == 0.0


def test_cer_ignores_capitalization():
    assert CERMetric().compute("As Rosas", "as rosas") == 0.0


def test_cer_penalizes_accent_difference():
    result = CERMetric().compute("nao", "não")
    assert result > 0.0
