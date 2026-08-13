import asyncio
import os
import subprocess
import uuid
from pathlib import Path

import redis.asyncio as redis

from app.core.config import get_settings

# Generous margin over analysis_service.py's 300s pipeline deadline —
# covers time spent queued behind other tasks plus Celery retries —
# without leaving orphaned audio in Redis for long after a crash.
_AUDIO_REDIS_TTL_SECONDS = 3600


def _temp_dir() -> Path:
    path = Path(get_settings().temp_audio_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _redis_key(recording_id: str) -> str:
    return f"audio:{recording_id}"


async def store_audio_bytes(recording_id: str, data: bytes) -> None:
    """api and worker are separate Fly Machines with independent local
    disks — a path written by save_upload_and_normalize() on one is
    invisible to the other (confirmed in production: worker raised
    FileNotFoundError reading a path the api process had written).
    Redis is the one thing both processes already share (same
    REDIS_URL, also the Celery broker), so the normalized bytes ride
    through there instead; see materialize_audio_from_redis()."""
    client = redis.from_url(get_settings().redis_url)
    try:
        await client.set(_redis_key(recording_id), data, ex=_AUDIO_REDIS_TTL_SECONDS)
    finally:
        await client.aclose()


async def materialize_audio_from_redis(recording_id: str) -> str | None:
    """Worker-side counterpart to store_audio_bytes() — fetches the bytes
    and writes them to a fresh local temp file on THIS machine, since
    ffmpeg/torchaudio/soundfile all need a real path, not bytes. Returns
    None if the key is missing (already consumed, or its TTL expired)."""
    client = redis.from_url(get_settings().redis_url)
    try:
        data = await client.get(_redis_key(recording_id))
    finally:
        await client.aclose()
    if data is None:
        return None
    path = _temp_dir() / f"{uuid.uuid4()}.wav"
    path.write_bytes(data)
    return str(path)


async def delete_audio_bytes(recording_id: str) -> None:
    """Best-effort — safe to call even if the key was never set or
    already consumed/expired."""
    client = redis.from_url(get_settings().redis_url)
    try:
        await client.delete(_redis_key(recording_id))
    finally:
        await client.aclose()


async def save_upload_and_normalize(raw_bytes: bytes, *, original_filename: str) -> str:
    """§11.4: iPhone Safari (mp4/AAC) and Chrome (webm/opus) upload
    different formats — normalize to 16kHz/16bit/mono WAV (§3.4, matches
    Azure's native recommended format) via ffmpeg before anything else
    touches the file. Writes into the local temp dir of whichever
    process calls this — the caller is responsible for getting the
    result to wherever it needs to go next (e.g. recordings.py hands the
    bytes to store_audio_bytes() for the worker to pick up; voice
    enrollment consumes the path itself, same-process, no handoff
    needed).

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
