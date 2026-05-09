from pydantic import BaseModel, Field


class LoggingConfig(BaseModel):
    mode: str = "normal"
    output_file: str = "logs/run.log"


class RetryConfig(BaseModel):
    max_attempts: int = 3
    backoff_factor: float = 2.0


class TranscriptionConfig(BaseModel):
    provider: str = "whisper"
    model: str = "whisper-1"
    transcription_prompt: str | None = None
    voice_isolation: bool = False


class RefinementConfig(BaseModel):
    provider: str
    model: str
    prompt_file: str
    temperature: float = 0.0


class DriveConfig(BaseModel):
    credentials_path: str = "credentials.json"
    token_path: str = "token.json"
    audio_dir: str = "data/inputs"


class ExperimentConfig(BaseModel):
    experiment_name: str
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    transcription: TranscriptionConfig = Field(default_factory=TranscriptionConfig)
    refinement: list[RefinementConfig] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    catalog_path: str = "data/catalogo.csv"
    drive: DriveConfig = Field(default_factory=DriveConfig)
    results_path: str = "results"
