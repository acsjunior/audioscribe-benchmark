from typing import Literal

from pydantic import BaseModel, Field, model_validator


class LoggingConfig(BaseModel):
    mode: str = "normal"
    output_file: str = "logs/run.log"


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_factor: float = 2.0


class TranscriptionConfig(BaseModel):
    # whisper = API de transcrição da OpenAI; google / openai-audio = LLM multimodal (E6)
    provider: Literal["whisper", "google", "openai-audio"] = "whisper"
    model: str = "whisper-1"
    transcription_prompt: str | None = None
    audio_preprocessing: Literal["demucs", "noisereduce", "deepfilternet"] | None = None
    runs: int = Field(default=1, ge=1)
    cache: bool = True
    # Padrão: <pai de drive.audio_dir>/transcriptions (ex.: data/transcriptions)
    cache_dir: str | None = None
    # Adiciona o método "consensus": a transcrição mais central entre as rodadas (exige runs >= 3)
    consensus: bool = False

    @model_validator(mode="after")
    def _consensus_needs_runs(self) -> "TranscriptionConfig":
        if self.consensus and self.runs < 3:
            raise ValueError("transcription.consensus exige transcription.runs >= 3")
        return self


class RefinementConfig(BaseModel):
    provider: str
    model: str
    prompt_file: str
    temperature: float = 0.0


class DriveConfig(BaseModel):
    credentials_path: str = "credentials.json"
    token_path: str = "token.json"
    audio_dir: str = "data/inputs"


class AnalysisConfig(BaseModel):
    bootstrap_samples: int = Field(default=10000, ge=100)
    confidence: float = Field(default=0.95, gt=0.0, lt=1.0)
    # Piora (na métrica) acima da qual uma avaliação conta como falha grave.
    severe_failure_threshold: float = Field(default=0.2, gt=0.0)
    seed: int = 0
    length_ratio_min: float = Field(default=0.7, gt=0.0)
    length_ratio_max: float = Field(default=1.3, gt=1.0)


class ExperimentConfig(BaseModel):
    experiment_name: str
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    refinement: list[RefinementConfig] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    catalog_path: str = "data/catalogo.csv"
    split: Literal["dev", "test", "all"] = "dev"
    analysis: AnalysisConfig = Field(default_factory=AnalysisConfig)
    drive: DriveConfig = Field(default_factory=DriveConfig)
    results_path: str = "results"
