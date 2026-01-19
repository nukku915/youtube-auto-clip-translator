"""プロジェクト履歴管理モジュール."""

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import List, Optional


@dataclass
class ProjectRecord:
    """プロジェクト記録."""

    id: str
    video_title: str
    video_id: str
    url: str
    subtitle_path: str
    srt_path: str
    output_dir: str
    created_at: str
    target_language: str = "ja"
    thumbnail_url: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ProjectRecord":
        return cls(**data)


class ProjectHistory:
    """プロジェクト履歴管理クラス."""

    def __init__(self, history_file: Optional[Path] = None):
        """初期化.

        Args:
            history_file: 履歴ファイルパス
        """
        if history_file is None:
            # デフォルトは出力ディレクトリ内
            self.history_file = Path("./output/history.json")
        else:
            self.history_file = history_file

        self._records: List[ProjectRecord] = []
        self._load()

    def _load(self) -> None:
        """履歴を読み込み."""
        if not self.history_file.exists():
            self._records = []
            return

        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self._records = [
                    ProjectRecord.from_dict(item)
                    for item in data.get("projects", [])
                ]
        except Exception:
            self._records = []

    def _save(self) -> None:
        """履歴を保存."""
        self.history_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "projects": [r.to_dict() for r in self._records]
        }

        with open(self.history_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def add(
        self,
        video_title: str,
        video_id: str,
        url: str,
        subtitle_path: Path,
        srt_path: Path,
        output_dir: Path,
        target_language: str = "ja",
        thumbnail_url: Optional[str] = None,
    ) -> ProjectRecord:
        """プロジェクトを追加.

        Args:
            video_title: 動画タイトル
            video_id: 動画ID
            url: YouTube URL
            subtitle_path: 字幕ファイルパス
            srt_path: SRTファイルパス
            output_dir: 出力ディレクトリ
            target_language: 翻訳先言語
            thumbnail_url: サムネイルURL

        Returns:
            追加したProjectRecord
        """
        record = ProjectRecord(
            id=f"{video_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}",
            video_title=video_title,
            video_id=video_id,
            url=url,
            subtitle_path=str(subtitle_path),
            srt_path=str(srt_path),
            output_dir=str(output_dir),
            created_at=datetime.now().isoformat(),
            target_language=target_language,
            thumbnail_url=thumbnail_url,
        )

        # 同じvideo_idの古い記録を削除（最新のみ保持）
        self._records = [r for r in self._records if r.video_id != video_id]

        # 先頭に追加
        self._records.insert(0, record)

        # 最大50件に制限
        self._records = self._records[:50]

        self._save()
        return record

    def get_all(self) -> List[ProjectRecord]:
        """全てのプロジェクトを取得.

        Returns:
            プロジェクトのリスト（新しい順）
        """
        return self._records.copy()

    def get_recent(self, count: int = 5) -> List[ProjectRecord]:
        """最近のプロジェクトを取得.

        Args:
            count: 取得件数

        Returns:
            プロジェクトのリスト
        """
        return self._records[:count]

    def get_by_id(self, project_id: str) -> Optional[ProjectRecord]:
        """IDでプロジェクトを取得.

        Args:
            project_id: プロジェクトID

        Returns:
            ProjectRecord または None
        """
        for record in self._records:
            if record.id == project_id:
                return record
        return None

    def delete(self, project_id: str) -> bool:
        """プロジェクトを削除.

        Args:
            project_id: プロジェクトID

        Returns:
            削除成功時True
        """
        original_count = len(self._records)
        self._records = [r for r in self._records if r.id != project_id]

        if len(self._records) < original_count:
            self._save()
            return True
        return False

    def clear(self) -> None:
        """全履歴をクリア."""
        self._records = []
        self._save()
