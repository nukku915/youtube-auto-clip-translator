"""データモデル."""
from .analysis import (
    AnalysisResult,
    Chapter,
    FullAnalysisResult,
    Highlight,
    HighlightType,
    TitleSuggestion,
)
from .project import (
    EditSegment,
    ExportConfig,
    ExportResult,
    Project,
    ProjectInfo,
    ProjectStatus,
)
from .subtitle import (
    SubtitleEntry,
    SubtitleFormat,
    SubtitlePosition,
    SubtitleResult,
    SubtitleStyleConfig,
    SubtitleTextConfig,
    SubtitleTimingConfig,
)
from .transcription import (
    TranscriptionResult,
    TranscriptionSegment,
    TranslatedSegment,
    TranslationResult,
    WordInfo,
)
from .video import (
    DownloadResult,
    VideoFormat,
    VideoInfo,
    VideoMetadata,
    VideoQuality,
)

__all__ = [
    # video
    "VideoMetadata",
    "VideoFormat",
    "VideoQuality",
    "VideoInfo",
    "DownloadResult",
    # transcription
    "WordInfo",
    "TranscriptionSegment",
    "TranscriptionResult",
    "TranslatedSegment",
    "TranslationResult",
    # analysis
    "HighlightType",
    "Highlight",
    "Chapter",
    "AnalysisResult",
    "TitleSuggestion",
    "FullAnalysisResult",
    # subtitle
    "SubtitleFormat",
    "SubtitlePosition",
    "SubtitleStyleConfig",
    "SubtitleEntry",
    "SubtitleResult",
    "SubtitleTimingConfig",
    "SubtitleTextConfig",
    # project
    "ProjectStatus",
    "EditSegment",
    "ExportConfig",
    "Project",
    "ProjectInfo",
    "ExportResult",
]
