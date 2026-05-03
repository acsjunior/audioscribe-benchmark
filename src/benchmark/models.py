from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SongData:
    song_id: str
    titulo: str
    autoria: str
    interpretacao: str
    disco: str
    ano: str
    genero: str
    audio_path: Path
    ground_truth: str


@dataclass
class ExperimentResult:
    song_id: str
    titulo: str
    autoria: str
    interpretacao: str
    disco: str
    ano: str
    genero: str
    whisper_transcription: str
    refinement_provider: str | None
    refinement_model: str | None
    prompt_name: str | None
    prompt_file: str | None
    refined_transcription: str | None
    ground_truth: str
    metrics: dict[str, float] = field(default_factory=dict)
    error: str | None = None
    tokens_used: int | None = None
    response_time_ms: float | None = None

    @property
    def evaluated_transcription(self) -> str:
        return self.refined_transcription or self.whisper_transcription

    @property
    def experiment_label(self) -> str:
        if self.refinement_provider:
            return f"{self.refinement_provider}/{self.refinement_model} [{self.prompt_name}]"
        return "baseline (whisper only)"
