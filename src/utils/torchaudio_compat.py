"""torchaudio/torch互換性パッチ.

torchaudio 2.9.x で削除されたAPIの互換性shimを提供します。
PyTorch 2.6+ のweights_only問題も修正します。
whisperxをインポートする前にこのモジュールをインポートしてください。
"""

import torch
import torchaudio


def _patch_torch_load():
    """PyTorch 2.6+のweights_only問題を修正.

    torch.loadのデフォルトをweights_only=Falseに戻す。
    whisperx/pyannoteのモデルはtrustedなソースからのものなので安全。
    """
    _original_torch_load = torch.load

    def _patched_load(*args, **kwargs):
        # weights_onlyが明示的に指定されていない場合はFalseを使用
        if "weights_only" not in kwargs:
            kwargs["weights_only"] = False
        return _original_torch_load(*args, **kwargs)

    torch.load = _patched_load


def _patch_torchaudio():
    """torchaudioに互換性パッチを適用."""

    # AudioMetaData クラスが存在しない場合は追加
    if not hasattr(torchaudio, "AudioMetaData"):
        from dataclasses import dataclass

        @dataclass
        class AudioMetaData:
            """torchaudio.AudioMetaData互換クラス."""
            sample_rate: int
            num_frames: int
            num_channels: int
            bits_per_sample: int = 16
            encoding: str = "PCM_S"

        torchaudio.AudioMetaData = AudioMetaData

    # list_audio_backends関数が存在しない場合は追加
    if not hasattr(torchaudio, "list_audio_backends"):
        def list_audio_backends():
            """利用可能なバックエンドを返す（互換性shim）."""
            # 新しいtorchaudioではtorchcodecを使用
            return ["ffmpeg"]

        torchaudio.list_audio_backends = list_audio_backends

    # info関数が存在しない場合は追加
    if not hasattr(torchaudio, "info"):
        def info(uri, format=None, backend=None):
            """音声ファイルのメタデータを取得（互換性shim）.

            Args:
                uri: 音声ファイルパス
                format: フォーマット（未使用）
                backend: バックエンド（未使用）

            Returns:
                AudioMetaData: メタデータ
            """
            # torchaudio.loadで読み込んでメタデータを取得
            waveform, sample_rate = torchaudio.load(uri)
            num_channels, num_frames = waveform.shape

            return torchaudio.AudioMetaData(
                sample_rate=sample_rate,
                num_frames=num_frames,
                num_channels=num_channels,
            )

        torchaudio.info = info


# モジュールインポート時に自動的にパッチを適用
_patch_torch_load()
_patch_torchaudio()
