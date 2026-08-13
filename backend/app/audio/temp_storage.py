import asyncio
import os
import subprocess
import uuid
from pathlib import Path

from app.core.config import get_settings


def _temp_dir() -> Path:
    path = Path(get_settings().temp_audio_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


async def save_upload_and_normalize(raw_bytes: bytes, *, original_filename: str) -> str:
    """§11.4: iPhone Safari (mp4/AAC) and Chrome (webm/opus) upload
    different formats — normalize to 16kHz/16bit/mono WAV (§3.4, matches
    Azure's native recommended format) via ffmpeg before anything else
    touches the file. §11.5: this writes into the shared local-disk temp
    dir that both the API process and the Celery worker can see.

    This is called directly from the upload request handler (not just from
    the Celery worker), so the blocking ffmpeg call runs in a thread — a
    30-minute clip's ffmpeg pass would otherwise stall the whole event loop
    and every other concurrent request on this process."""
    temp_dir = _temp_dir()
    raw_suffix = Path(original_filename).suffix or ".webm"
    raw_path = temp_dir / f"{uuid.uuid4()}{raw_suffix}"
    raw_path.write_bytes(raw_bytes)

    # A fresh uuid, not raw_path.stem — if original_filename already ends
    # in .wav (raw_suffix == ".wav"), reusing the stem here would make
    # this identical to raw_path, handing ffmpeg the same file as both
    # -i and its output target.
    wav_path = temp_dir / f"{uuid.uuid4()}.wav"
    try:
        await asyncio.to_thread(
            subprocess.run,
            [
                "ffmpeg",
                "-y",
                "-i",
                str(raw_path),
                "-ar",
                "16000",
                "-ac",
                "1",
                "-sample_fmt",
                "s16",
                str(wav_path),
            ],
            check=True,
            capture_output=True,
        )
    finally:
        raw_path.unlink(missing_ok=True)

    return str(wav_path)


def delete_temp_file(path: str) -> None:
    """Best-effort cleanup — called from the worker's `finally` block
    (§11.5) and from the cleanup_worker safety-net sweep. Never raises on
    a missing file, since both callers may race to delete the same path."""
    Path(path).unlink(missing_ok=True)


def list_orphaned_paths(cutoff_seconds: int) -> list[str]:
    """Filesystem-level backstop for the DB-driven cleanup query in
    recording_repository — catches files that were written but never made
    it into a Recording row at all (e.g. crash between write and DB
    insert)."""
    import time

    now = time.time()
    temp_dir = _temp_dir()
    return [
        str(p)
        for p in temp_dir.glob("*.wav")
        if now - os.path.getmtime(p) > cutoff_seconds
    ]
