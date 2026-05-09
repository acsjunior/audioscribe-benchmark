import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from .config.schema import ExperimentConfig
from .dataset import load_catalog
from .gdrive import download_audio
from .metrics import get_metrics
from .models import ExperimentResult
from .refinement import get_refiner, load_prompt
from .refinement.base import BaseRefiner, PromptConfig
from .reporting.csv_reporter import write_csv
from .reporting.html_reporter import write_html
from .reporting.json_reporter import write_json
from .transcription.whisper import WhisperTranscriber
from .utils.retry import async_retry
from .noise_reduction import reduce_noise
from .voice_isolation import isolate_voice

logger = logging.getLogger("benchmark")


class Pipeline:
    def __init__(self, config: ExperimentConfig, drive_service=None) -> None:
        self.config = config
        self.drive_service = drive_service
        self.transcriber = WhisperTranscriber(
            model=config.transcription.model,
            prompt=config.transcription.transcription_prompt,
        )
        self.metrics = get_metrics(config.metrics)

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

    async def run(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = Path(self.config.results_path) / f"{self.config.experiment_name}_{timestamp}"
        run_dir.mkdir(parents=True, exist_ok=True)

        songs = load_catalog(self.config.catalog_path)
        logger.info(f"Catálogo carregado: {len(songs)} música(s)")

        audio_dir = Path(self.config.drive.audio_dir)
        audio_dir.mkdir(parents=True, exist_ok=True)

        transcribe_fn = self._with_retry(self.transcriber.transcribe)
        refiners = self._prepare_refiners()

        all_results: list[ExperimentResult] = []

        for i, song in enumerate(songs, 1):
            logger.info(f"[{i}/{len(songs)}] {song.interpretacao} — {song.titulo}")

            audio_path = self._resolve_audio_path(song.audio_filename)
            if not audio_path.exists():
                if self.drive_service is None:
                    logger.error(f"  Arquivo não encontrado e Google Drive não configurado: {audio_path}")
                    continue
                try:
                    download_audio(self.drive_service, song.audio_url, audio_path)
                    logger.info("  Download concluído")
                except Exception as e:
                    logger.error(f"  Download falhou: {e}")
                    continue
            else:
                logger.debug(f"  Usando cache: {audio_path.name}")

            preprocessing = self.config.transcription.audio_preprocessing
            if preprocessing == "demucs":
                try:
                    audio_path = isolate_voice(audio_path)
                except Exception as e:
                    logger.error(f"  Isolamento de voz falhou: {e}")
                    continue
            elif preprocessing == "noisereduce":
                try:
                    audio_path = reduce_noise(audio_path)
                except Exception as e:
                    logger.error(f"  Redução de ruído falhou: {e}")
                    continue

            try:
                transcription = await transcribe_fn(audio_path)
                logger.info("  Transcrição concluída")
            except Exception as e:
                logger.error(f"  Transcrição falhou após {self.config.retry.max_attempts} tentativa(s): {e}")
                continue

            all_results.append(ExperimentResult(
                song_id=song.song_id,
                titulo=song.titulo,
                autoria=song.autoria,
                interpretacao=song.interpretacao,
                disco=song.disco,
                ano=song.ano,
                genero=song.genero,
                whisper_transcription=transcription,
                refinement_provider=None,
                refinement_model=None,
                prompt_name=None,
                prompt_file=None,
                refined_transcription=None,
                ground_truth=song.ground_truth,
                metrics=self._compute_metrics(transcription, song.ground_truth),
            ))

            song_metadata = {
                "titulo": song.titulo,
                "autoria": song.autoria,
                "interpretacao": song.interpretacao,
                "ano": song.ano,
            }

            for j, (ref_config, refiner, prompt) in enumerate(refiners, 1):
                logger.info(
                    f"  [{j}/{len(refiners)}] "
                    f"{ref_config.provider}/{ref_config.model} [{ref_config.prompt_file}]"
                )
                try:
                    refine_fn = self._with_retry(refiner.refine)
                    ref_result = await refine_fn(transcription, prompt, song_metadata)

                    time_str = f"{ref_result.response_time_ms:.0f}ms" if ref_result.response_time_ms else "N/A"
                    logger.info(f"    OK — tokens: {ref_result.tokens_used}, tempo: {time_str}")

                    all_results.append(ExperimentResult(
                        song_id=song.song_id,
                        titulo=song.titulo,
                        autoria=song.autoria,
                        interpretacao=song.interpretacao,
                        disco=song.disco,
                        ano=song.ano,
                        genero=song.genero,
                        whisper_transcription=transcription,
                        refinement_provider=ref_config.provider,
                        refinement_model=ref_config.model,
                        prompt_name=prompt.name,
                        prompt_file=ref_config.prompt_file,
                        refined_transcription=ref_result.refined_text,
                        ground_truth=song.ground_truth,
                        metrics=self._compute_metrics(ref_result.refined_text, song.ground_truth),
                        tokens_used=ref_result.tokens_used,
                        response_time_ms=ref_result.response_time_ms,
                    ))

                except Exception as e:
                    logger.error(f"    Falhou: {e}")
                    all_results.append(ExperimentResult(
                        song_id=song.song_id,
                        titulo=song.titulo,
                        autoria=song.autoria,
                        interpretacao=song.interpretacao,
                        disco=song.disco,
                        ano=song.ano,
                        genero=song.genero,
                        whisper_transcription=transcription,
                        refinement_provider=ref_config.provider,
                        refinement_model=ref_config.model,
                        prompt_name=None,
                        prompt_file=ref_config.prompt_file,
                        refined_transcription=None,
                        ground_truth=song.ground_truth,
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
