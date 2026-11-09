from dataclasses import dataclass, field


@dataclass
class SongData:
    song_id: str
    titulo: str
    autoria: str
    interpretacao: str
    disco: str
    ano: str
    genero: str
    audio_url: str
    audio_filename: str
    ground_truth: str
    split: str = "dev"


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
    run: int = 1
    split: str = "dev"

    @property
    def evaluated_transcription(self) -> str:
        return self.refined_transcription or self.whisper_transcription

    @property
    def experiment_label(self) -> str:
        if self.refinement_provider:
            label = f"{self.refinement_provider}/{self.refinement_model}"
            return f"{label} [{self.prompt_name}]" if self.prompt_name else label
        return "baseline (whisper only)"
