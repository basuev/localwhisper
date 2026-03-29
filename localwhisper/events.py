from dataclasses import dataclass


@dataclass
class RecordingStarted:
    pass


@dataclass
class RecordingFailed:
    reason: str


@dataclass
class RecordingDone:
    audio_data: bytes
    duration: float


@dataclass
class TranscriptionStarted:
    pass


@dataclass
class TranscriptionDone:
    raw_text: str


@dataclass
class TranscriptionFailed:
    error: str


@dataclass
class PostProcessingStarted:
    pass


@dataclass
class PostProcessingDone:
    raw_text: str
    processed_text: str


@dataclass
class PostProcessingFailed:
    raw_text: str
    error: str


@dataclass
class Cancelled:
    stage: str


@dataclass
class FeedbackResult:
    added: list[tuple[str, str]]
    conflicts: list[tuple[str, str, str]]


@dataclass
class EngineReady:
    pass
