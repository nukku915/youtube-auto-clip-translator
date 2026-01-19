"""
処理中ビュー
============

動画処理の進捗を表示する画面。
"""

import asyncio
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Callable

import customtkinter as ctk

from ..theme import COLORS, SPACING, NaniTheme
from ..widgets import (
    NaniButton,
    NaniLabel,
    NaniCard,
    NaniProgressBar,
)
from .base import BaseView

if TYPE_CHECKING:
    from ..app import App


class ProcessingStep(Enum):
    """処理ステップ."""
    DOWNLOAD = "download"
    EXTRACT_AUDIO = "extract_audio"
    TRANSCRIBE = "transcribe"
    TRANSLATE = "translate"
    GENERATE_SUBTITLE = "generate_subtitle"


@dataclass
class StepStatus:
    """ステップのステータス."""
    step: ProcessingStep
    label: str
    status: str = "pending"  # pending, running, completed, error
    progress: float = 0.0
    message: str = ""


class ProcessingView(BaseView):
    """処理中ビュー."""

    def __init__(self, master, app: "App", **kwargs) -> None:
        self._url: str = ""
        self._target_language: str = "ja"
        self._is_processing: bool = False
        self._cancel_requested: bool = False
        self._step_widgets: dict = {}
        super().__init__(master, app, **kwargs)

    def _setup_ui(self) -> None:
        """UIを構築."""
        # グリッド設定
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)

        # 中央コンテナ
        center_container = ctk.CTkFrame(self, fg_color="transparent")
        center_container.grid(row=0, column=0)

        # タイトル
        self._title_label = NaniLabel(
            center_container,
            text="処理中...",
            variant="title",
        )
        self._title_label.pack(pady=(0, SPACING.MD))

        # 動画情報
        self._video_info_label = NaniLabel(
            center_container,
            text="",
            variant="secondary",
        )
        self._video_info_label.pack(pady=(0, SPACING.XL))

        # プログレスカード
        progress_card = NaniCard(center_container, width=500)
        progress_card.pack(pady=SPACING.MD)

        card_content = ctk.CTkFrame(progress_card, fg_color="transparent")
        card_content.pack(padx=SPACING.XL, pady=SPACING.XL, fill="both", expand=True)

        # 全体プログレスバー
        self._overall_progress = NaniProgressBar(card_content, width=450, height=12)
        self._overall_progress.pack(pady=(0, SPACING.SM))
        self._overall_progress.set(0)

        # 全体プログレスラベル
        self._overall_label = NaniLabel(
            card_content,
            text="0%",
            variant="secondary",
        )
        self._overall_label.pack(pady=(0, SPACING.XL))

        # 各ステップのステータス
        steps_frame = ctk.CTkFrame(card_content, fg_color="transparent")
        steps_frame.pack(fill="x")

        self._steps = [
            StepStatus(ProcessingStep.DOWNLOAD, "動画ダウンロード"),
            StepStatus(ProcessingStep.EXTRACT_AUDIO, "音声抽出"),
            StepStatus(ProcessingStep.TRANSCRIBE, "文字起こし"),
            StepStatus(ProcessingStep.TRANSLATE, "翻訳"),
            StepStatus(ProcessingStep.GENERATE_SUBTITLE, "字幕生成"),
        ]

        for step in self._steps:
            step_frame = ctk.CTkFrame(steps_frame, fg_color="transparent")
            step_frame.pack(fill="x", pady=SPACING.XS)

            # ステータスアイコン
            status_label = NaniLabel(
                step_frame,
                text="○",
                variant="muted",
            )
            status_label.pack(side="left", padx=(0, SPACING.SM))

            # ステップ名
            name_label = NaniLabel(
                step_frame,
                text=step.label,
                variant="default",
            )
            name_label.pack(side="left")

            # メッセージ
            message_label = NaniLabel(
                step_frame,
                text="",
                variant="muted",
            )
            message_label.pack(side="right")

            self._step_widgets[step.step] = {
                "status": status_label,
                "name": name_label,
                "message": message_label,
            }

        # 現在の処理メッセージ
        self._current_message = NaniLabel(
            card_content,
            text="",
            variant="muted",
        )
        self._current_message.pack(pady=(SPACING.XL, 0))

        # ボタンフレーム
        button_frame = ctk.CTkFrame(center_container, fg_color="transparent")
        button_frame.pack(pady=SPACING.XL)

        # キャンセルボタン
        self._cancel_button = NaniButton(
            button_frame,
            text="キャンセル",
            variant="secondary",
            command=self._on_cancel_clicked,
        )
        self._cancel_button.pack(side="left", padx=SPACING.SM)

        # 完了後のボタン（初期は非表示）
        self._home_button = NaniButton(
            button_frame,
            text="ホームに戻る",
            variant="primary",
            command=self._on_home_clicked,
        )

    def on_show(self, url: str = "", target_language: str = "ja", **kwargs) -> None:
        """ビュー表示時."""
        self._url = url
        self._target_language = target_language
        self._cancel_requested = False

        # UIをリセット
        self._title_label.configure(text="処理中...")
        self._video_info_label.configure(text=url[:50] + "..." if len(url) > 50 else url)
        self._overall_progress.set(0)
        self._overall_label.configure(text="0%")
        self._current_message.configure(text="処理を開始しています...")

        # ステップをリセット
        for step in self._steps:
            step.status = "pending"
            step.progress = 0.0
            step.message = ""
            self._update_step_ui(step)

        # ボタン状態
        self._cancel_button.pack(side="left", padx=SPACING.SM)
        self._home_button.pack_forget()

        # 処理を開始
        self._start_processing()

    def _update_step_ui(self, step: StepStatus) -> None:
        """ステップのUIを更新."""
        widgets = self._step_widgets.get(step.step)
        if not widgets:
            return

        status_icons = {
            "pending": ("○", COLORS.TEXT_MUTED),
            "running": ("●", COLORS.PRIMARY),
            "completed": ("✓", COLORS.SUCCESS),
            "error": ("✗", COLORS.DANGER),
        }

        icon, color = status_icons.get(step.status, ("○", COLORS.TEXT_MUTED))
        widgets["status"].configure(text=icon, text_color=color)
        widgets["message"].configure(text=step.message)

    def _update_overall_progress(self) -> None:
        """全体の進捗を更新."""
        total_steps = len(self._steps)
        completed = sum(1 for s in self._steps if s.status == "completed")
        running_progress = sum(s.progress for s in self._steps if s.status == "running")

        overall = (completed + running_progress / 100) / total_steps
        self._overall_progress.set(overall)
        self._overall_label.configure(text=f"{int(overall * 100)}%")

    def _start_processing(self) -> None:
        """処理を開始."""
        if self._is_processing:
            return

        self._is_processing = True
        future = self.app.run_async(self._process_video())

        def on_done(f):
            self._is_processing = False
            try:
                result = f.result()
                self.after(0, lambda: self._on_processing_complete(result))
            except Exception as e:
                self.after(0, lambda: self._on_processing_error(str(e)))

        future.add_done_callback(on_done)

    async def _process_video(self) -> dict:
        """動画を処理."""
        from src.core import (
            AudioProcessor,
            OllamaClient,
            SubtitleGenerator,
            Transcriber,
            Translator,
            VideoFetcher,
        )
        from src.models import SubtitleFormat

        output_dir = Path("./output")
        output_dir.mkdir(parents=True, exist_ok=True)

        result = {
            "success": False,
            "video_path": None,
            "subtitle_path": None,
            "error": None,
        }

        try:
            # 1. 動画ダウンロード
            self._set_step_running(ProcessingStep.DOWNLOAD)
            fetcher = VideoFetcher(download_dir=output_dir / "downloads")

            def download_progress(progress: float, message: str):
                self.after(0, lambda: self._update_step_progress(
                    ProcessingStep.DOWNLOAD, progress, message
                ))

            download_result = await fetcher.download(
                self._url,
                progress_callback=download_progress,
            )

            if self._cancel_requested:
                raise Exception("処理がキャンセルされました")

            if not download_result.success:
                raise Exception(f"ダウンロード失敗: {download_result.error}")

            video_path = download_result.video_path
            metadata = download_result.metadata
            result["video_path"] = video_path

            self._set_step_completed(ProcessingStep.DOWNLOAD)
            self.after(0, lambda: self._video_info_label.configure(
                text=metadata.title[:50] + "..." if len(metadata.title) > 50 else metadata.title
            ))

            # 2. 音声抽出
            self._set_step_running(ProcessingStep.EXTRACT_AUDIO)
            audio_processor = AudioProcessor(temp_dir=output_dir / "temp")

            def audio_progress(progress: float, message: str):
                self.after(0, lambda: self._update_step_progress(
                    ProcessingStep.EXTRACT_AUDIO, progress, message
                ))

            audio_path = await audio_processor.extract_audio(
                video_path,
                progress_callback=audio_progress,
            )

            if self._cancel_requested:
                raise Exception("処理がキャンセルされました")

            self._set_step_completed(ProcessingStep.EXTRACT_AUDIO)

            # 3. 文字起こし
            self._set_step_running(ProcessingStep.TRANSCRIBE)
            transcriber = Transcriber()

            def transcribe_progress(progress: float, message: str):
                self.after(0, lambda: self._update_step_progress(
                    ProcessingStep.TRANSCRIBE, progress, message
                ))

            try:
                transcription = await transcriber.transcribe(
                    audio_path,
                    progress_callback=transcribe_progress,
                )
            finally:
                transcriber.unload_model()

            if self._cancel_requested:
                raise Exception("処理がキャンセルされました")

            self._set_step_completed(ProcessingStep.TRANSCRIBE)

            # 4. 翻訳
            self._set_step_running(ProcessingStep.TRANSLATE)
            ollama_client = OllamaClient()

            if not await ollama_client.is_available():
                self.after(0, lambda: self._current_message.configure(
                    text="警告: Ollamaが利用できません。翻訳をスキップします。"
                ))
                translation = None
                self._set_step_completed(ProcessingStep.TRANSLATE, "スキップ")
            else:
                translator = Translator(
                    llm_client=ollama_client,
                    target_language=self._target_language,
                )

                def translate_progress(progress: float, message: str):
                    self.after(0, lambda: self._update_step_progress(
                        ProcessingStep.TRANSLATE, progress, message
                    ))

                translation = await translator.translate_transcription(
                    transcription,
                    progress_callback=translate_progress,
                )
                self._set_step_completed(ProcessingStep.TRANSLATE)

            if self._cancel_requested:
                raise Exception("処理がキャンセルされました")

            # 5. 字幕生成
            self._set_step_running(ProcessingStep.GENERATE_SUBTITLE)

            if translation:
                subtitle_generator = SubtitleGenerator()

                # ASS形式
                ass_path = output_dir / f"{metadata.video_id}.ass"
                subtitle_result = subtitle_generator.generate(
                    translation,
                    ass_path,
                    output_format=SubtitleFormat.ASS,
                )
                result["subtitle_path"] = subtitle_result.file_path

                # SRT形式も生成
                srt_path = output_dir / f"{metadata.video_id}.srt"
                subtitle_generator.convert_format(
                    ass_path,
                    SubtitleFormat.SRT,
                    srt_path,
                )
                result["srt_path"] = srt_path

            self._set_step_completed(ProcessingStep.GENERATE_SUBTITLE)
            result["success"] = True
            result["video_title"] = metadata.title
            result["video_id"] = metadata.video_id
            result["output_dir"] = output_dir

            # 履歴に保存
            from src.core.project_history import ProjectHistory
            history = ProjectHistory()
            history.add(
                video_title=metadata.title,
                video_id=metadata.video_id,
                url=self._url,
                subtitle_path=result["subtitle_path"],
                srt_path=result.get("srt_path", result["subtitle_path"]),
                output_dir=output_dir,
                target_language=self._target_language,
                thumbnail_url=metadata.thumbnail_url if hasattr(metadata, 'thumbnail_url') else None,
            )

        except Exception as e:
            result["error"] = str(e)
            # 現在実行中のステップをエラーにする
            for step in self._steps:
                if step.status == "running":
                    step.status = "error"
                    step.message = "エラー"
                    self.after(0, lambda s=step: self._update_step_ui(s))

        return result

    def _set_step_running(self, step_type: ProcessingStep) -> None:
        """ステップを実行中に設定."""
        for step in self._steps:
            if step.step == step_type:
                step.status = "running"
                step.progress = 0.0
                step.message = "処理中..."
                self.after(0, lambda s=step: self._update_step_ui(s))
                self.after(0, lambda: self._current_message.configure(
                    text=f"{step.label}を実行中..."
                ))
                break

    def _set_step_completed(self, step_type: ProcessingStep, message: str = "完了") -> None:
        """ステップを完了に設定."""
        for step in self._steps:
            if step.step == step_type:
                step.status = "completed"
                step.progress = 100.0
                step.message = message
                self.after(0, lambda s=step: self._update_step_ui(s))
                self.after(0, self._update_overall_progress)
                break

    def _update_step_progress(
        self,
        step_type: ProcessingStep,
        progress: float,
        message: str,
    ) -> None:
        """ステップの進捗を更新."""
        for step in self._steps:
            if step.step == step_type:
                step.progress = progress
                step.message = message
                self._update_step_ui(step)
                self._update_overall_progress()
                break

    def _on_processing_complete(self, result: dict) -> None:
        """処理完了時."""
        if result["success"]:
            # 結果画面に遷移
            self.navigate_to(
                "result",
                video_title=result.get("video_title", ""),
                video_id=result.get("video_id", ""),
                subtitle_path=result.get("subtitle_path"),
                srt_path=result.get("srt_path"),
                output_dir=result.get("output_dir"),
            )
        else:
            self._title_label.configure(text="処理エラー")
            self._current_message.configure(text=f"エラー: {result['error']}")
            self._current_message.configure(text_color=COLORS.DANGER)

            # ボタンを切り替え
            self._cancel_button.pack_forget()
            self._home_button.pack(side="left", padx=SPACING.SM)

    def _on_processing_error(self, error: str) -> None:
        """処理エラー時."""
        self._title_label.configure(text="処理エラー")
        self._current_message.configure(text=f"エラー: {error}")
        self._current_message.configure(text_color=COLORS.DANGER)

        # ボタンを切り替え
        self._cancel_button.pack_forget()
        self._home_button.pack(side="left", padx=SPACING.SM)

    def _on_cancel_clicked(self) -> None:
        """キャンセルボタンクリック時."""
        self._cancel_requested = True
        self._current_message.configure(text="キャンセル中...")

    def _on_home_clicked(self) -> None:
        """ホームボタンクリック時."""
        self.navigate_to("home")
