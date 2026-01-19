"""YouTube Auto Clip Translator - CLI エントリーポイント."""
import argparse
import asyncio
import sys
from pathlib import Path


def print_progress(progress: float, message: str) -> None:
    """進捗を表示."""
    bar_length = 30
    filled = int(bar_length * progress / 100)
    bar = "=" * filled + "-" * (bar_length - filled)
    print(f"\r[{bar}] {progress:.1f}% - {message}", end="", flush=True)
    if progress >= 100:
        print()


async def process_video(
    url: str,
    target_language: str = "ja",
    output_dir: Path = Path("./output"),
) -> None:
    """動画を処理.

    Args:
        url: YouTube URL
        target_language: 翻訳先言語
        output_dir: 出力ディレクトリ
    """
    from src.core import (
        AudioProcessor,
        OllamaClient,
        SubtitleGenerator,
        Transcriber,
        Translator,
        VideoAnalyzer,
        VideoFetcher,
    )
    from src.models import SubtitleFormat

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"処理開始: {url}")
    print(f"翻訳先言語: {target_language}")
    print(f"出力先: {output_dir}")
    print("-" * 50)

    # 1. 動画ダウンロード
    print("\n[1/5] 動画をダウンロード中...")
    fetcher = VideoFetcher(download_dir=output_dir / "downloads")

    download_result = await fetcher.download(
        url,
        progress_callback=print_progress,
    )

    if not download_result.success:
        print(f"エラー: ダウンロード失敗 - {download_result.error}")
        return

    video_path = download_result.video_path
    metadata = download_result.metadata
    print(f"タイトル: {metadata.title}")
    print(f"長さ: {metadata.duration:.0f}秒")

    # 2. 音声抽出
    print("\n[2/5] 音声を抽出中...")
    audio_processor = AudioProcessor(temp_dir=output_dir / "temp")
    audio_path = await audio_processor.extract_audio(
        video_path,
        progress_callback=print_progress,
    )

    # 3. 文字起こし
    print("\n[3/5] 文字起こし中...")
    transcriber = Transcriber()

    try:
        transcription = await transcriber.transcribe(
            audio_path,
            progress_callback=print_progress,
        )
        print(f"検出言語: {transcription.language}")
        print(f"セグメント数: {len(transcription.segments)}")
    except Exception as e:
        print(f"エラー: 文字起こし失敗 - {e}")
        return
    finally:
        transcriber.unload_model()

    # 4. 翻訳
    print("\n[4/5] 翻訳中...")

    # Ollamaクライアントを作成
    ollama_client = OllamaClient()

    if not await ollama_client.is_available():
        print("警告: Ollamaが利用できません。翻訳をスキップします。")
        print("Ollamaを起動してください: ollama serve")
        translation = None
    else:
        translator = Translator(
            llm_client=ollama_client,
            target_language=target_language,
        )

        try:
            translation = await translator.translate_transcription(
                transcription,
                progress_callback=print_progress,
            )
            print(f"翻訳完了: {len(translation.segments)}セグメント")
        except Exception as e:
            print(f"エラー: 翻訳失敗 - {e}")
            translation = None

    # 5. 字幕生成
    print("\n[5/5] 字幕を生成中...")

    if translation:
        subtitle_generator = SubtitleGenerator()

        # ASS形式
        ass_path = output_dir / f"{metadata.video_id}.ass"
        result = subtitle_generator.generate(
            translation,
            ass_path,
            output_format=SubtitleFormat.ASS,
        )
        print(f"字幕生成完了: {result.file_path}")

        # SRT形式も生成
        srt_path = output_dir / f"{metadata.video_id}.srt"
        subtitle_generator.convert_format(
            ass_path,
            SubtitleFormat.SRT,
            srt_path,
        )
        print(f"SRT変換完了: {srt_path}")

    # 完了
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"動画: {video_path}")
    if translation:
        print(f"字幕: {output_dir / f'{metadata.video_id}.ass'}")
        print(f"字幕: {output_dir / f'{metadata.video_id}.srt'}")


async def analyze_video(url: str, output_dir: Path = Path("./output")) -> None:
    """動画を分析.

    Args:
        url: YouTube URL
        output_dir: 出力ディレクトリ
    """
    from src.core import (
        AudioProcessor,
        OllamaClient,
        Transcriber,
        VideoAnalyzer,
        VideoFetcher,
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"分析開始: {url}")
    print("-" * 50)

    # 1. 動画情報取得
    print("\n[1/4] 動画情報を取得中...")
    fetcher = VideoFetcher(download_dir=output_dir / "downloads")
    info = await fetcher.get_video_info(url)
    print(f"タイトル: {info.title}")
    print(f"長さ: {info.duration:.0f}秒")

    # 2. 動画ダウンロード
    print("\n[2/4] 動画をダウンロード中...")
    download_result = await fetcher.download(
        url,
        progress_callback=print_progress,
    )

    if not download_result.success:
        print(f"エラー: ダウンロード失敗 - {download_result.error}")
        return

    video_path = download_result.video_path

    # 3. 音声抽出 & 文字起こし
    print("\n[3/4] 文字起こし中...")
    audio_processor = AudioProcessor(temp_dir=output_dir / "temp")
    audio_path = await audio_processor.extract_audio(video_path)

    transcriber = Transcriber()

    try:
        transcription = await transcriber.transcribe(
            audio_path,
            progress_callback=print_progress,
        )
    except Exception as e:
        print(f"エラー: 文字起こし失敗 - {e}")
        return
    finally:
        transcriber.unload_model()

    # 4. AI分析
    print("\n[4/4] AI分析中...")
    ollama_client = OllamaClient()

    if not await ollama_client.is_available():
        print("警告: Ollamaが利用できません。")
        return

    analyzer = VideoAnalyzer(ollama_client)

    try:
        analysis = await analyzer.analyze(
            transcription,
            progress_callback=print_progress,
        )
    except Exception as e:
        print(f"エラー: 分析失敗 - {e}")
        return

    # 結果表示
    print("\n" + "=" * 50)
    print("分析結果:")
    print(f"\n要約:\n{analysis.summary}")

    print(f"\nチャプター ({len(analysis.chapters)}件):")
    for ch in analysis.chapters:
        start = f"{int(ch.start // 60):02d}:{int(ch.start % 60):02d}"
        print(f"  [{start}] {ch.title}")

    print(f"\n見どころ ({len(analysis.highlights)}件):")
    for h in analysis.highlights:
        start = f"{int(h.start // 60):02d}:{int(h.start % 60):02d}"
        print(f"  [{start}] {h.title} ({h.highlight_type.value}, score: {h.score:.2f})")


def main() -> None:
    """メイン関数."""
    parser = argparse.ArgumentParser(
        description="YouTube Auto Clip Translator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
例:
  yact https://www.youtube.com/watch?v=XXXXX
  yact https://youtu.be/XXXXX -l en
  yact --analyze https://www.youtube.com/watch?v=XXXXX
""",
    )

    parser.add_argument(
        "url",
        help="YouTube動画のURL",
    )

    parser.add_argument(
        "-l", "--language",
        default="ja",
        help="翻訳先言語 (デフォルト: ja)",
    )

    parser.add_argument(
        "-o", "--output",
        default="./output",
        help="出力ディレクトリ (デフォルト: ./output)",
    )

    parser.add_argument(
        "--analyze",
        action="store_true",
        help="分析のみ実行（翻訳なし）",
    )

    args = parser.parse_args()

    try:
        if args.analyze:
            asyncio.run(analyze_video(args.url, Path(args.output)))
        else:
            asyncio.run(process_video(args.url, args.language, Path(args.output)))
    except KeyboardInterrupt:
        print("\n処理を中断しました。")
        sys.exit(1)
    except Exception as e:
        print(f"\nエラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
