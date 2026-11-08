import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .config.schema import ExperimentConfig
from .dataset import load_catalog
from .deep_filter import filter_noise
from .gdrive import download_audio
from .metrics import get_metrics
from .models import ExperimentResult, SongData
from .noise_reduction import reduce_noise
from .refinement import get_refiner, load_prompt
from .refinement.base import BaseRefiner, PromptConfig
from .reporting.csv_reporter import write_csv
from .reporting.html_reporter import write_html
from .reporting.json_reporter import write_json
from .transcription.cache import TranscriptionCache, file_sha256
from .transcription.whisper import WhisperTranscriber, effective_prompt
from .utils.retry import async_retry
from .voice_isolation import isolate_voice

logger = logging.getLogger("benchmark")

def _get_preprocessor(name: str) -> tuple[Callable[[Path], Path], str]:
    # Montado a cada chamada para respeitar os nomes do módulo (permite patch nos testes).
    return {
        "demucs": (isolate_voice, "Isolamento de voz"),
        "noisereduce": (reduce_noise, "Redução de ruído"),
        "deepfilternet": (filter_noise, "Filtragem DeepFilterNet"),
    }[name]


class Pipeline:
    def __init__(self, config: ExperimentConfig, drive_service=None) -> None:
        self.config = config
        self.drive_service = drive_service
        self.transcriber = WhisperTranscriber(
            model=config.transcription.model,
            prompt=config.transcription.transcription_prompt,
        )
        self.metrics = get_metrics(config.metrics)
        self.cache = self._build_cache() if config.transcription.cache else None

    def _build_cache(self) -> TranscriptionCache:
        tcfg = self.config.transcription
        root = (
            Path(tcfg.cache_dir)
            if tcfg.cache_dir
            else Path(self.config.drive.audio_dir).parent / "transcriptions"
        )
        return TranscriptionCache(
            root=root,
            model=tcfg.model,
            prompt=effective_prompt(tcfg.model, tcfg.transcription_prompt),
            preprocessing=tcfg.audio_preprocessing,
        )

    def _with_retry(self, func: Callable) -> Callable:
        return async_retry(
            max_attempts=self.config.retry.max_attempts,
            backoff_factor=self.config.retry.backoff_factor,
        )(func)

    def _compute_metrics(self, hypothesis: str, reference: str) -> dict[str, float | None]:
        results: dict[str, float | None] = {}
        for metric in self.metrics:
            try:
                results[metric.name] = metric.compute(hypothesis, reference)
            except Exception as e:
                logger.warning(f"Metric {metric.name} failed: {e}")
                results[metric.name] = None
        return results

    def _prepare_refiners(self) -> list[tuple[object, BaseRefiner, PromptConfig]]:
        refiners = []
        for ref_config in self.config.refinement:
            prompt = load_prompt(ref_config.prompt_file)
            refiner = get_refiner(ref_config.provider, ref_config.model, ref_config.temperature)
            refiners.append((ref_config, refiner, prompt))
        return refiners

    def _resolve_audio_path(self, audio_filename: str) -> Path:
        return Path(self.config.drive.audio_dir) / audio_filename

    def _select_songs(self, songs: list[SongData]) -> list[SongData]:
        split = self.config.split
        if split == "all":
            return songs
        return [s for s in songs if s.split == split]

    def _prepare_audio(self, song: SongData) -> Path | None:
        """Baixa (se preciso) e pré-processa o áudio. Retorna None se falhar."""
        audio_path = self._resolve_audio_path(song.audio_filename)
        if not audio_path.exists():
            if self.drive_service is None:
                logger.error(
                    f"  Arquivo não encontrado e Google Drive não configurado: {audio_path}"
                )
                return None
            try:
                download_audio(self.drive_service, song.audio_url, audio_path)
                logger.info("  Download concluído")
            except Exception as e:
                logger.error(f"  Download falhou: {e}")
                return None
        else:
            logger.debug(f"  Usando cache: {audio_path.name}")

        preprocessing = self.config.transcription.audio_preprocessing
        if preprocessing:
            func, label = _get_preprocessor(preprocessing)
            try:
                audio_path = func(audio_path)
            except Exception as e:
                logger.error(f"  {label} falhou: {e}")
                return None

        return audio_path

    async def _transcribe_run(
        self,
        song: SongData,
        run: int,
        audio_path: Path,
        audio_sha256: str | None,
        transcribe_fn: Callable,
    ) -> str | None:
        """Transcrição de uma rodada, do cache ou da API. Retorna None se falhar."""
        runs = self.config.transcription.runs
        prefix = f"  Rodada {run}/{runs}: " if runs > 1 else "  "

        if self.cache is not None:
            cached = self.cache.load(song.song_id, run, audio_sha256)
            if cached is not None:
                logger.info(f"{prefix}transcrição do cache")
                return cached

        try:
            transcription = await transcribe_fn(audio_path)
        except Exception as e:
            attempts = self.config.retry.max_attempts
            logger.error(f"{prefix}transcrição falhou após {attempts} tentativa(s): {e}")
            return None

        if self.cache is not None:
            self.cache.save(song.song_id, run, transcription, audio_path, audio_sha256)
        logger.info(f"{prefix}transcrição concluída")
        return transcription

    def _result(self, song: SongData, run: int, transcription: str, **kwargs) -> ExperimentResult:
        defaults = {
            "refinement_provider": None,
            "refinement_model": None,
            "prompt_name": None,
            "prompt_file": None,
            "refined_transcription": None,
        }
        defaults.update(kwargs)
        return ExperimentResult(
            song_id=song.song_id,
            titulo=song.titulo,
            autoria=song.autoria,
            interpretacao=song.interpretacao,
            disco=song.disco,
            ano=song.ano,
            genero=song.genero,
            whisper_transcription=transcription,
            ground_truth=song.ground_truth,
            run=run,
            split=song.split,
            **defaults,
        )

    async def run(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(self.config.results_path) / f"{self.config.experiment_name}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        catalog = load_catalog(self.config.catalog_path)
        songs = self._select_songs(catalog)
        logger.info(
            f"Catálogo carregado: {len(catalog)} música(s); "
            f"split '{self.config.split}': {len(songs)} música(s)"
        )
        if self.cache is not None:
            logger.info(f"Cache de transcrições: {self.cache.dir}")

        audio_dir = Path(self.config.drive.audio_dir)
        audio_dir.mkdir(parents=True, exist_ok=True)

        transcribe_fn = self._with_retry(self.transcriber.transcribe)
        refiners = self._prepare_refiners()
        runs = self.config.transcription.runs

        all_results: list[ExperimentResult] = []

        for i, song in enumerate(songs, 1):
            logger.info(f"[{i}/{len(songs)}] {song.interpretacao} — {song.titulo}")

            audio_path = self._prepare_audio(song)
            if audio_path is None:
                continue

            audio_sha256 = file_sha256(audio_path) if self.cache is not None else None

            song_metadata = {
                "titulo": song.titulo,
                "autoria": song.autoria,
                "interpretacao": song.interpretacao,
                "ano": song.ano,
            }

            for run in range(1, runs + 1):
                transcription = await self._transcribe_run(
                    song, run, audio_path, audio_sha256, transcribe_fn
                )
                if transcription is None:
                    continue

                all_results.append(self._result(
                    song, run, transcription,
                    metrics=self._compute_metrics(transcription, song.ground_truth),
                ))

                for j, (ref_config, refiner, prompt) in enumerate(refiners, 1):
                    logger.info(
                        f"    [{j}/{len(refiners)}] "
                        f"{ref_config.provider}/{ref_config.model} [{ref_config.prompt_file}]"
                    )
                    try:
                        refine_fn = self._with_retry(refiner.refine)
                        ref_result = await refine_fn(transcription, prompt, song_metadata)

                        time_str = (
                            f"{ref_result.response_time_ms:.0f}ms"
                            if ref_result.response_time_ms
                            else "N/A"
                        )
                        tokens = ref_result.tokens_used
                        logger.info(f"      OK — tokens: {tokens}, tempo: {time_str}")

                        all_results.append(self._result(
                            song, run, transcription,
                            refinement_provider=ref_config.provider,
                            refinement_model=ref_config.model,
                            prompt_name=prompt.name,
                            prompt_file=ref_config.prompt_file,
                            refined_transcription=ref_result.refined_text,
                            metrics=self._compute_metrics(
                                ref_result.refined_text, song.ground_truth
                            ),
                            tokens_used=ref_result.tokens_used,
                            response_time_ms=ref_result.response_time_ms,
                        ))

                    except Exception as e:
                        logger.error(f"      Falhou: {e}")
                        all_results.append(self._result(
                            song, run, transcription,
                            refinement_provider=ref_config.provider,
                            refinement_model=ref_config.model,
                            prompt_file=ref_config.prompt_file,
                            error=str(e),
                        ))

        if all_results:
            write_csv(all_results, run_dir / "results.csv")
            write_json(all_results, run_dir / "results.json")
            write_html(all_results, run_dir / "report.html", self.config.experiment_name)
            logger.info(f"Resultados salvos em: {run_dir}")
        else:
            logger.warning("Nenhum resultado para salvar.")

        return run_dir
