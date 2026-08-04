import asyncio
import subprocess
from pathlib import Path

from app.integrations.stt.base import STTSegment


async def slice_audio_by_speaker(wav_path: str, segments: list[STTSegment]) -> dict[str, str]:
    """§3.3: diarization happens once (in STT); this cuts the single mixed
    recording into one concatenated clip per speaker_label, which is what
    speaker-id and prosody providers each expect to receive — never the
    raw mix (§3.2, §3.3)."""
    return await asyncio.to_thread(_slice_sync, wav_path, segments)


def _slice_sync(wav_path: str, segments: list[STTSegment]) -> dict[str, str]:
    temp_dir = Path(wav_path).parent
    stem = Path(wav_path).stem

    by_speaker: dict[str, list[STTSegment]] = {}
    for seg in segments:
        by_speaker.setdefault(seg.speaker_label, []).append(seg)

    result: dict[str, str] = {}
    for speaker, segs in by_speaker.items():
        clip_paths: list[Path] = []
        for i, seg in enumerate(segs):
            clip_path = temp_dir / f"{stem}_{speaker}_{i}.wav"
            subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-i",
                    wav_path,
                    "-ss",
                    f"{seg.start_ms / 1000:.3f}",
                    "-to",
                    f"{seg.end_ms / 1000:.3f}",
                    str(clip_path),
                ],
                check=True,
                capture_output=True,
            )
            clip_paths.append(clip_path)

        if len(clip_paths) == 1:
            result[speaker] = str(clip_paths[0])
            continue

        concat_list = temp_dir / f"{stem}_{speaker}_concat.txt"
        concat_list.write_text("\n".join(f"file '{p}'" for p in clip_paths))
        combined_path = temp_dir / f"{stem}_{speaker}_combined.wav"
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_list),
                "-c",
                "copy",
                str(combined_path),
            ],
            check=True,
            capture_output=True,
        )
        for p in clip_paths:
            p.unlink(missing_ok=True)
        concat_list.unlink(missing_ok=True)
        result[speaker] = str(combined_path)

    return result


def delete_speaker_clips(paths: dict[str, str]) -> None:
    for path in paths.values():
        Path(path).unlink(missing_ok=True)
