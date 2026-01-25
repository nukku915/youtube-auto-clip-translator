#!/usr/bin/env python3
"""
YouTube切り抜き + 話者識別 + 音声認識 + 自動学習 + Gemini翻訳 システム

使用方法:
    # 通常処理（指定区間を切り抜き）
    python clip_with_speaker.py <YouTube URL> <開始時間> <終了時間>

    # Gemini翻訳を使用（高精度）
    python clip_with_speaker.py <YouTube URL> <開始時間> <終了時間> --gemini

    # チームボイス自動検出（長い動画から盛り上がり部分を検出）
    python clip_with_speaker.py <YouTube URL> --detect

    # 学習モード（処理後に確認・修正）
    python clip_with_speaker.py <YouTube URL> <開始時間> <終了時間> --learn

    # 直近の結果を修正して学習
    python clip_with_speaker.py --correct

    # エンベディング品質チェック＆自動改善
    python clip_with_speaker.py --improve T1

オプション:
    --team T1       チームを指定（T1, GenG, HLE, DK, KT）
    --output xxx    出力ファイル名
    --gemini        Gemini APIで高精度翻訳
    --detect        チームボイス自動検出モード
    --learn         処理後に学習モードを起動
    --auto-learn    自動学習モード（高スコアのみ）
    --correct       直近の結果を修正して学習
    --improve TEAM  指定チームのエンベディングを自動改善
"""

import sys
import os
import re
import subprocess
import argparse
import numpy as np
import torchaudio
import torch
import json
import whisper
import threading
from datetime import datetime
from pathlib import Path
import yt_dlp
from googletrans import Translator
from moviepy import VideoFileClip, TextClip, CompositeVideoClip
from speechbrain.inference.speaker import EncoderClassifier
from lol_dictionary import correct_text, create_correction_dict, correct_korean_asr, correct_japanese_post

# 自動収集モジュール（オプション）
try:
    from auto_collect_voice import (
        collect_with_diarization,
        load_existing_embeddings,
        create_backup,
        list_backups,
        restore_backup,
        restore_player_embedding
    )
    AUTO_COLLECT_AVAILABLE = True
except ImportError:
    AUTO_COLLECT_AVAILABLE = False

# Demucs音声分離（オプション）
try:
    from demucs.pretrained import get_model
    from demucs.apply import apply_model
    DEMUCS_AVAILABLE = True
except ImportError:
    DEMUCS_AVAILABLE = False

# 設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDINGS_DIR = os.path.join(BASE_DIR, 'data/speaker_embeddings_v2')
CACHE_DIR = os.path.join(BASE_DIR, 'data/speechbrain_cache')
TEMP_DIR = os.path.join(BASE_DIR, 'downloads/temp')
OUTPUT_DIR = os.path.expanduser('~/Downloads')
DB_PATH = os.path.join(BASE_DIR, 'data/speaker_database.json')
HISTORY_PATH = os.path.join(BASE_DIR, 'data/learning_history.json')
CUSTOM_DICT_PATH = os.path.join(BASE_DIR, 'data/custom_lol_terms.json')

# 自動改善設定
AUTO_IMPROVE_CONFIG = {
    'enabled': True,  # 品質が低い場合に自動でエンベディングを改善
    'threshold': 0.5,  # 低品質セグメントがこの割合を超えたら改善
    'cooldown': 3600,  # 同じチームの改善間隔（秒）
}
AUTO_IMPROVE_LOG_PATH = os.path.join(BASE_DIR, 'data/auto_improve_log.json')

# Gemini翻訳用のLoLコンテキスト
LOL_TRANSLATION_CONTEXT = """あなたはLeague of Legends (LoL)のプロチームのチームボイス（試合中のコミュニケーション）を翻訳するエキスパートです。

## 重要なLoL用語
### チャンピオン
- 오리/오리아나 = オリアナ
- 그웬/가위 = グウェン（가위はグウェンのQスキル「ハサミ」）
- 그라가스/그라겟 = グラガス
- 애니/언니 = アニー（언니「姉さん」はアニーの愛称）
- 리신/리 신 = リー・シン
- 야스오/야스 = ヤスオ
- 요네 = ヨネ

### アイテム
- 존야 = ゾーニャの砂時計
- 가엔/수호천사 = ガーディアンエンジェル (GA)
- 얼어붙은 심장 = フローズンハート

### ゲーム用語
- 바론 = バロン
- 드래곤/용 = ドラゴン
- 한타 = 集団戦
- 갱 = ガンク
- 합류 = 合流
- 구도 = 構図/ポジショニング
- 콜 = コール（報告）
- 궁 = ウルト
- 볼 = ボール（オリアナのスキル）
- 딜 = ダメージ
- 탱킹 = タンキング

### サモナースペル
- 점멸/플래시 = フラッシュ
- 점화 = イグナイト
- 강타 = スマイト
- 텔포 = テレポート

## 翻訳ルール
1. チームボイスは短く簡潔に（話し言葉で）
2. ゲーム用語はカタカナでそのまま使用
3. 感情やテンションを維持
4. 「です/ます」は使わず、カジュアルな口調で
5. 日本語翻訳のみを出力（説明不要）
6. **会話の受け答えを意識**：質問→回答、提案→賛否、報告→リアクションの流れを自然に
7. 返事・相槌は自然な日本語で（알았어→おっけ/了解、응→うん、그래→そうだね）"""

# チームボイス検出プロンプト
TEAMVOICE_DETECT_PROMPT = """Analyze the following transcript from a League of Legends (LOL) game video.

Your task is to identify moments where TEAM MEMBERS are communicating with each other during gameplay.

Look for:
- Player callouts and communication (e.g., "行くぞ", "下がって", "フラッシュない", "ult行く")
- Reactions during fights (e.g., "ナイス!", "やばい", "うわー", laughing, excited shouts)
- Team coordination moments (e.g., "ドラゴン取ろう", "バロン", "プッシュして")
- Emotional reactions (hype moments, frustration, celebration after kills)

DO NOT include:
- Calm analytical commentary or explanations of the game
- Tutorial-style explanations
- Post-game analysis discussions

Transcript:
{transcript}

Return a JSON array of team voice moments with this exact format:
[
  {{
    "start": <start_time_in_seconds>,
    "end": <end_time_in_seconds>,
    "title": "<short description of the moment>",
    "description": "<what's happening - callout, reaction, coordination, etc.>",
    "type": "<type: callout|reaction|coordination|celebration|other>",
    "score": <importance/intensity score 0.0-1.0, higher = more energetic/important>
  }}
]

Requirements:
- Find all moments with team communication or reactions
- Each clip should be 5-30 seconds long
- Prioritize energetic, exciting, or funny moments
- Return ONLY valid JSON, no other text"""


def time_to_sec(t: str) -> int:
    """時間文字列を秒に変換"""
    parts = t.split(":")
    if len(parts) == 2:
        return int(parts[0]) * 60 + int(parts[1])
    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])


def sec_to_time(sec: float) -> str:
    """秒を時間文字列に変換"""
    m, s = divmod(int(sec), 60)
    return f"{m}:{s:02d}"


def load_database():
    """選手データベースを読み込み"""
    with open(DB_PATH, 'r') as f:
        return json.load(f)


def save_database(db):
    """選手データベースを保存"""
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_history():
    """学習履歴を読み込み"""
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, 'r') as f:
            return json.load(f)
    return {'sessions': []}


def save_history(history):
    """学習履歴を保存"""
    with open(HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def load_custom_dict():
    """カスタムLoL用語辞書を読み込み"""
    if os.path.exists(CUSTOM_DICT_PATH):
        with open(CUSTOM_DICT_PATH, 'r') as f:
            return json.load(f)
    return {'terms': {}, 'learned_count': 0}


def save_custom_dict(custom_dict):
    """カスタムLoL用語辞書を保存"""
    with open(CUSTOM_DICT_PATH, 'w') as f:
        json.dump(custom_dict, f, indent=2, ensure_ascii=False)


def get_merged_corrections():
    """基本辞書とカスタム辞書を統合"""
    corrections = create_correction_dict()
    custom = load_custom_dict()
    corrections.update(custom.get('terms', {}))
    return corrections


def apply_lol_corrections(text: str) -> str:
    """LoL用語を修正"""
    corrections = get_merged_corrections()
    return correct_text(text, corrections)


def get_gemini_api_key():
    """Gemini APIキーを取得"""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        # .envファイルから読み込み試行
        env_path = os.path.join(BASE_DIR, '.env')
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    if line.startswith('GEMINI_API_KEY='):
                        api_key = line.strip().split('=', 1)[1].strip('"\'')
                        break
    return api_key


def translate_with_gemini(text: str, speaker: str = "") -> str:
    """Gemini APIで翻訳（LoLコンテキスト付き）"""
    api_key = get_gemini_api_key()
    if not api_key:
        print("   ⚠️ GEMINI_API_KEY未設定、googletransにフォールバック")
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        speaker_context = f"（話者: {speaker}）" if speaker else ""

        prompt = f"""{LOL_TRANSLATION_CONTEXT}

## 翻訳対象
韓国語: {text}
{speaker_context}

## 出力
日本語翻訳のみ:"""

        response = model.generate_content(prompt)
        result = response.text.strip()

        # マークダウン装飾を除去
        result = re.sub(r'\*\*(.+?)\*\*', r'\1', result)
        result = re.sub(r'「(.+?)」', r'\1', result)

        # 複数行の場合は最初の行のみ
        lines = result.split('\n')
        return lines[0].strip() if lines else result

    except Exception as e:
        print(f"   ⚠️ Gemini翻訳エラー: {e}")
        return None


def detect_team_from_title(title: str) -> str:
    """動画タイトルからチームを検出"""
    title_upper = title.upper()
    teams = ['T1', 'GENG', 'GEN.G', 'HLE', 'DK', 'KT', 'DRX', 'NS', 'BRO', 'LSB']
    team_map = {'GENG': 'GenG', 'GEN.G': 'GenG', 'T1': 'T1', 'HLE': 'HLE', 'DK': 'DK', 'KT': 'KT'}

    if ' VS ' in title_upper or ' VS.' in title_upper:
        for team in teams:
            idx = title_upper.find(team)
            vs_idx = title_upper.find(' VS')
            if idx != -1 and idx < vs_idx:
                return team_map.get(team, team)

    for team in teams:
        if team in title_upper:
            return team_map.get(team, team)

    return None


def download_clip(url: str, start_sec: int = None, end_sec: int = None) -> tuple:
    """YouTube動画をダウンロード（区間指定可）"""
    os.makedirs(TEMP_DIR, exist_ok=True)
    clip_path = os.path.join(TEMP_DIR, 'clip.mp4')

    title = None
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': clip_path,
        'quiet': True,
        'no_warnings': True,
    }

    # 区間指定がある場合
    if start_sec is not None and end_sec is not None:
        ydl_opts['download_ranges'] = lambda info, ydl: [{'start_time': start_sec, 'end_time': end_sec}]
        ydl_opts['force_keyframes_at_cuts'] = True

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get('title', 'Unknown')
        ydl.download([url])

    return clip_path, title


def extract_audio(video_path: str) -> str:
    """動画から音声を抽出"""
    audio_path = os.path.join(TEMP_DIR, 'audio.wav')
    subprocess.run([
        'ffmpeg', '-y', '-i', video_path,
        '-vn', '-acodec', 'pcm_s16le', '-ar', '16000', '-ac', '1', audio_path
    ], capture_output=True)
    return audio_path


def separate_vocals(audio_path: str) -> str:
    """Demucsで音声からボーカルを分離（ゲーム音を除去）"""
    if not DEMUCS_AVAILABLE:
        print("   ⚠️ Demucs未インストール。音声分離をスキップ")
        print("   インストール: pip install demucs")
        return audio_path

    try:
        print("   🎵 音声分離中（Demucs）...")

        # 音声読み込み（44.1kHz必要）
        waveform, sr = torchaudio.load(audio_path)

        # 44.1kHzにリサンプリング（Demucsの要件）
        if sr != 44100:
            resampler = torchaudio.transforms.Resample(sr, 44100)
            waveform = resampler(waveform)

        # ステレオに変換
        if waveform.shape[0] == 1:
            waveform = waveform.repeat(2, 1)

        # Demucsモデル読み込み
        model = get_model('htdemucs')
        model.eval()

        # GPU使用可能ならGPU
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
        model.to(device)
        waveform = waveform.to(device)

        # バッチ次元追加
        waveform = waveform.unsqueeze(0)

        # 音声分離実行
        with torch.no_grad():
            sources = apply_model(model, waveform, device=device)

        # ボーカルトラック抽出 (index 3 = vocals)
        vocals = sources[0, 3]  # [2, samples]

        # モノラルに変換
        vocals_mono = vocals.mean(dim=0, keepdim=True)

        # 16kHzにリサンプリング
        resampler_down = torchaudio.transforms.Resample(44100, 16000)
        vocals_16k = resampler_down(vocals_mono.cpu())

        # 保存
        vocals_path = os.path.join(TEMP_DIR, 'vocals.wav')
        torchaudio.save(vocals_path, vocals_16k, 16000)

        print("   ✅ 音声分離完了")
        return vocals_path

    except Exception as e:
        print(f"   ⚠️ 音声分離エラー: {e}")
        return audio_path


def load_speaker_embeddings(team: str = None, db: dict = None) -> dict:
    """話者エンベディングを読み込み"""
    embeddings = {}

    if team and db and team in db['teams']:
        team_players = [p.lower() for p in db['teams'][team]['players']]
        for f in os.listdir(EMBEDDINGS_DIR):
            if f.endswith('.npy'):
                name = f.replace('.npy', '')
                if name in team_players:
                    embeddings[name] = np.load(os.path.join(EMBEDDINGS_DIR, f))
    else:
        for f in os.listdir(EMBEDDINGS_DIR):
            if f.endswith('.npy'):
                name = f.replace('.npy', '')
                embeddings[name] = np.load(os.path.join(EMBEDDINGS_DIR, f))

    return embeddings


def transcribe_audio(audio_path: str, language: str = "ko", model_size: str = "base") -> list:
    """Whisperで音声認識

    Args:
        audio_path: 音声ファイルパス
        language: 言語コード
        model_size: モデルサイズ (tiny, base, small, medium, large)
    """
    print(f"   Whisper {model_size}モデル使用")
    model = whisper.load_model(model_size)
    result = model.transcribe(audio_path, language=language)
    return result['segments']


def translate_to_japanese(text: str, speaker: str = "", use_gemini: bool = False,
                         use_papago: bool = False,
                         context_before: str = "", context_after: str = "") -> str:
    """韓国語を日本語に翻訳し、LoL用語を修正

    Args:
        text: 翻訳対象テキスト
        speaker: 話者名
        use_gemini: Gemini APIを使用するか
        use_papago: Papago APIを使用するか（推奨）
        context_before: 前のセグメントのテキスト（文脈用）
        context_after: 後のセグメントのテキスト（文脈用）
    """
    if not text or len(text.strip()) == 0:
        return text

    # Papago翻訳を試行（韓日特化、最高精度）
    if use_papago:
        try:
            from papago_translator import translate_korean_to_japanese
            result = translate_korean_to_japanese(text)
            if result and result != text:
                return apply_lol_corrections(result)
        except Exception as e:
            print(f"   ⚠️ Papago翻訳エラー: {e}")

    # Gemini翻訳を試行（文脈付き）
    if use_gemini:
        result = translate_with_gemini_context(text, speaker, context_before, context_after)
        if result:
            return apply_lol_corrections(result)

    # googletransにフォールバック
    try:
        translator = Translator()
        result = translator.translate(text, src='ko', dest='ja')
        translated = result.text
        return apply_lol_corrections(translated)
    except Exception as e:
        return text


def translate_with_gemini_context(text: str, speaker: str = "",
                                   context_before: str = "", context_after: str = "") -> str:
    """Gemini APIで文脈付き翻訳"""
    api_key = get_gemini_api_key()
    if not api_key:
        return None

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        speaker_context = f"話者: {speaker}" if speaker else ""

        # 文脈を構築
        context_parts = []
        if context_before:
            context_parts.append(f"前の発言: {context_before}")
        if context_after:
            context_parts.append(f"後の発言: {context_after}")
        context_str = "\n".join(context_parts) if context_parts else ""

        prompt = f"""{LOL_TRANSLATION_CONTEXT}

## 翻訳対象
{speaker_context}
韓国語: {text}

{f"## 文脈（参考）" if context_str else ""}
{context_str}

## 出力
日本語翻訳のみ（説明不要）:"""

        response = model.generate_content(prompt)
        result = response.text.strip()

        # マークダウン装飾を除去
        result = re.sub(r'\*\*(.+?)\*\*', r'\1', result)
        result = re.sub(r'「(.+?)」', r'\1', result)

        # 複数行の場合は最初の行のみ
        lines = result.split('\n')
        return lines[0].strip() if lines else result

    except Exception as e:
        # フォールバック：文脈なしで翻訳
        return translate_with_gemini(text, speaker)


def review_translations_with_context(segments: list, use_gemini: bool = True) -> list:
    """
    全体の文脈を見て翻訳を見直し・修正

    チームボイスは会話の流れがあるため、個別の翻訳だけでは
    文脈に合わない不自然な翻訳になることがある。
    全セグメントを一覧して、文脈に合わない翻訳を修正する。

    Args:
        segments: 翻訳済みセグメントのリスト
        use_gemini: Gemini APIを使用するか

    Returns:
        文脈修正済みのセグメントリスト
    """
    if not use_gemini or not segments:
        return segments

    api_key = get_gemini_api_key()
    if not api_key:
        print("   ⚠️ GEMINI_API_KEY未設定、文脈レビューをスキップ")
        return segments

    print("   🔍 全体の文脈を分析中...")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # 会話全体を構築
        conversation_lines = []
        for i, seg in enumerate(segments):
            speaker = seg.get('speaker', '???')
            speaker = speaker.capitalize() if speaker else '???'
            text_ja = seg.get('text_ja', seg.get('text', ''))
            text_ko = seg.get('text', '')
            time_str = sec_to_time(seg['start'])
            conversation_lines.append(f"{i+1}. [{time_str}] {speaker}: {text_ja} (韓国語: {text_ko})")

        conversation_text = "\n".join(conversation_lines)

        prompt = f"""あなたはLeague of Legends (LoL)のプロチームのチームボイス翻訳を校正する専門家です。

## タスク
以下のチームボイス翻訳を全体の文脈を見て確認し、**チームの会話・受け答えの流れ**を重視して修正してください。

## 最重要：チームの受け答えを翻訳する
チームボイスは**複数人の会話**です。誰かの発言に対して別のメンバーが応答します。
- 質問 → 回答の流れを自然に
- 提案 → 賛成/反対の流れを自然に
- 指示 → 了解/実行の流れを自然に
- 状況報告 → リアクションの流れを自然に

例：
- A「行く？」→ B「行こう！」（受け答え）
- A「バロン見て」→ B「おっけ」→ C「俺がタンクする」（複数人の会話）
- A「フラッシュない」→ B「じゃあ狙おう」（情報共有→判断）

## チームボイスの特徴
- 試合中の短いコールアウト（オリアナ！グウェン！など）
- 状況報告（来てる、いない、TP使った）
- 指示（下がって、合流して、行こう）
- リアクション（ナイス！やば！うわー）
- 集団戦中の叫び声や盛り上がり
- **相手の発言への返事**（おっけ、了解、分かった、いいね）

## よくある誤訳パターン
1. 「など言って」「として」など、文末が不自然
2. 試合中のコールに合わない丁寧な文（「私が」→「俺が」など）
3. 同じ内容の繰り返しコールが異なる意味に翻訳される
4. 会話の流れが途切れる翻訳（前の発言を受けていない）

## 絶対に守るルール
- チャンピオン名（オリアナ、グウェン、グラガス、ヤスオ、ヨネなど）は絶対に変更禁止
- 「オリアナ」を「右」に変えてはいけない（これは誤りです）
- 「オリアナ、オリアナ」「オリアナ見て」などはそのまま維持すること
- 試合中は敵チャンピオン名を叫ぶのが普通なので、チャンピオン名はそのままにする

## 現在の翻訳
{conversation_text}

## 指示
1. 上記の翻訳を**会話の流れ**として読む
2. 誰かの発言に対する応答として不自然な翻訳を特定
3. チームの受け答えとして自然になるよう修正
4. 修正が必要な行のみ、以下のJSON形式で出力

出力形式（修正または削除が必要な行のみ）:
```json
[
  {{"index": 1, "action": "fix", "original": "元の翻訳", "corrected": "修正後の翻訳", "reason": "修正理由"}},
  {{"index": 2, "action": "remove", "original": "元の翻訳", "reason": "削除理由"}},
  ...
]
```

重要：
- action は "fix"（修正）または "remove"（削除）
- "fix" の場合、correctedには翻訳テキストのみを入れてください（話者名は含めない）
- **会話の受け答えを意識**：前の発言を受けた応答として自然か？
- 質問には回答、提案には賛否、報告にはリアクションがあるはず
- 会話の流れに合わない不自然なセグメントは "remove" で削除指定
- 例：集団戦の最後に突然「分かる？」「本当に？」など脈絡のない発言
- 例：音声認識の誤りで意味不明な文
- 修正・削除不要の場合は空配列 `[]` を返してください"""

        response = model.generate_content(prompt)
        result = response.text.strip()

        # JSONをパース
        corrections = _parse_context_corrections(result)

        if not corrections:
            print("   ✅ 文脈上の問題なし")
            return segments

        # 修正・削除を適用
        fix_count = sum(1 for c in corrections if c.get('action') == 'fix')
        remove_count = sum(1 for c in corrections if c.get('action') == 'remove')
        print(f"   📝 文脈レビュー: 修正{fix_count}件, 削除{remove_count}件")

        for corr in corrections:
            idx = corr.get('index', 0) - 1  # 1-indexed to 0-indexed
            if 0 <= idx < len(segments):
                action = corr.get('action', 'fix')
                original = segments[idx].get('text_ja', '')
                reason = corr.get('reason', '')

                if action == 'remove':
                    # 削除マークを付ける
                    segments[idx]['removed'] = True
                    print(f"      [{idx+1}] ❌ 削除: {original}")
                    if reason:
                        print(f"          理由: {reason}")
                else:
                    # 修正
                    corrected = corr.get('corrected', '')

                    # 話者名プレフィックスを除去（Geminiが含めてしまった場合）
                    if corrected:
                        corrected = re.sub(r'^[A-Za-z]+[：:]\s*', '', corrected)

                    if corrected and corrected != original:
                        segments[idx]['text_ja'] = corrected
                        segments[idx]['context_corrected'] = True
                        print(f"      [{idx+1}] {original} → {corrected}")
                        if reason:
                            print(f"          理由: {reason}")

        # 削除マークのついたセグメントを除外
        segments = [s for s in segments if not s.get('removed', False)]

        return segments

    except Exception as e:
        print(f"   ⚠️ 文脈レビューエラー: {e}")
        return segments


def _parse_context_corrections(text: str) -> list:
    """文脈修正のJSON応答をパース"""
    text = text.strip()

    # コードブロック内のJSONを抽出
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    # 配列を探す
    if "[" in text and "]" in text:
        start = text.index("[")
        end = text.rindex("]") + 1
        text = text[start:end]

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []
        return data
    except json.JSONDecodeError:
        return []


def merge_conversation_segments(segments: list, gap_threshold: float = 1.0,
                                  same_speaker_gap: float = 2.0) -> list:
    """
    会話の流れに沿ってセグメントをマージ

    Args:
        segments: 元のセグメントリスト
        gap_threshold: 話者が変わっても統合する最大ギャップ（秒）
        same_speaker_gap: 同じ話者の発言を統合する最大ギャップ（秒）

    Returns:
        マージされたセグメントリスト
    """
    if not segments:
        return []

    merged = []
    current = {
        'start': segments[0]['start'],
        'end': segments[0]['end'],
        'texts': [segments[0].get('text_ja', segments[0]['text'])],
        'speakers': [segments[0]['speaker']],
        'scores': [segments[0]['score']],
    }

    for seg in segments[1:]:
        gap = seg['start'] - current['end']
        same_speaker = seg['speaker'] == current['speakers'][-1]

        # マージ条件:
        # 1. 同じ話者で gap < same_speaker_gap
        # 2. 違う話者でも gap < gap_threshold（会話の流れを保つ）
        should_merge = False

        if same_speaker and gap < same_speaker_gap:
            should_merge = True
        elif gap < gap_threshold and len(current['texts']) < 4:
            # 短いギャップで、まだ統合数が少ない場合
            should_merge = True

        if should_merge:
            current['end'] = seg['end']
            current['texts'].append(seg.get('text_ja', seg['text']))
            current['speakers'].append(seg['speaker'])
            current['scores'].append(seg['score'])
        else:
            # 現在のセグメントを確定
            merged.append(_finalize_merged_segment(current))
            # 新しいセグメント開始
            current = {
                'start': seg['start'],
                'end': seg['end'],
                'texts': [seg.get('text_ja', seg['text'])],
                'speakers': [seg['speaker']],
                'scores': [seg['score']],
            }

    # 最後のセグメント
    merged.append(_finalize_merged_segment(current))

    return merged


def _finalize_merged_segment(current: dict) -> dict:
    """マージされたセグメントを確定"""
    from collections import Counter

    # 最も多い話者を選択
    speaker_counts = Counter(current['speakers'])
    main_speaker = speaker_counts.most_common(1)[0][0]

    # テキストを結合
    combined_text = ' '.join(current['texts'])

    # 平均スコア
    avg_score = sum(current['scores']) / len(current['scores'])

    # 話者が複数いる場合のマーク
    unique_speakers = list(set(current['speakers']))
    if len(unique_speakers) > 1:
        speaker_display = f"{main_speaker}ら"
    else:
        speaker_display = main_speaker

    return {
        'start': current['start'],
        'end': current['end'],
        'text_ja': combined_text,
        'speaker': speaker_display,
        'score': avg_score,
        'segment_count': len(current['texts']),
    }


# ロール別の特徴的なコール（韓国語）
ROLE_KEYWORDS = {
    'jungle': ['갱', '정글', '카운터', '오브젝트', '드래곤', '바론', '헤럴드', '크랩'],
    'support': ['와드', '핑크', '시야', '로밍', '힐', '실드'],
    'mid': ['미드', '로밍', '솔킬'],
    'top': ['탑', '텔', 'tp', '스플릿'],
    'adc': ['딜', '포지션', 'cs'],
}

# チームのロール情報
TEAM_ROLES = {
    'T1': {'Doran': 'top', 'Oner': 'jungle', 'Faker': 'mid', 'Peyz': 'adc', 'Keria': 'support'},
    'GenG': {'Kiin': 'top', 'Canyon': 'jungle', 'Chovy': 'mid', 'Ruler': 'adc', 'Lehends': 'support'},
    'HLE': {'Zeus': 'top', 'Peanut': 'jungle', 'Zeka': 'mid', 'Viper': 'adc', 'Delight': 'support'},
}


def identify_speaker_for_segment(waveform, sr: int, start: float, end: float,
                                  encoder, embeddings: dict, text: str = "", team: str = None) -> tuple:
    """セグメントの話者を識別（改善版）"""
    start_sample = int(start * sr)
    end_sample = int(end * sr)

    if end_sample - start_sample < sr:
        center = (start_sample + end_sample) // 2
        start_sample = max(0, center - sr // 2)
        end_sample = min(waveform.shape[1], center + sr // 2)

    segment_audio = waveform[:, start_sample:end_sample]

    if segment_audio.shape[1] < sr // 2:
        return None, 0.0, None

    emb = encoder.encode_batch(segment_audio).squeeze().numpy()

    # 全選手のスコアを計算
    scores = {}
    for name, ref_emb in embeddings.items():
        sim = np.dot(emb, ref_emb) / (np.linalg.norm(emb) * np.linalg.norm(ref_emb))
        scores[name] = sim

    # スコア順でソート
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_name, best_score = sorted_scores[0]
    second_name, second_score = sorted_scores[1] if len(sorted_scores) > 1 else (None, 0)

    # 僅差判定（0.08以内）
    confidence = 'high' if best_score > 0.5 else 'medium' if best_score > 0.4 else 'low'

    if best_score - second_score < 0.08:
        confidence = 'uncertain'

        # テキストベースのロール推測で補正
        if text and team and team in TEAM_ROLES:
            text_lower = text.lower()
            role_scores = {name: 0 for name in embeddings.keys()}

            for role, keywords in ROLE_KEYWORDS.items():
                for kw in keywords:
                    if kw in text_lower:
                        # このロールの選手にボーナス
                        for player, player_role in TEAM_ROLES.get(team, {}).items():
                            if player_role == role and player.lower() in embeddings:
                                role_scores[player.lower()] += 0.05

            # ボーナスを適用
            for name in [best_name, second_name]:
                if name and name.lower() in role_scores:
                    if role_scores[name.lower()] > 0:
                        scores[name] += role_scores[name.lower()]

            # 再計算
            sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
            best_name, best_score = sorted_scores[0]

    return best_name, float(best_score), confidence


def update_speaker_embedding(speaker: str, audio_path: str, start: float, end: float,
                             encoder, weight_new: float = 0.3):
    """確認されたセグメントでエンベディングを更新"""
    waveform, sr = torchaudio.load(audio_path)
    start_sample = int(start * sr)
    end_sample = int(end * sr)

    # 最低1秒のセグメント
    if end_sample - start_sample < sr:
        return False, "セグメントが短すぎます"

    segment = waveform[:, start_sample:end_sample]
    new_emb = encoder.encode_batch(segment).squeeze().numpy()

    # 既存のエンベディングを読み込み
    emb_path = os.path.join(EMBEDDINGS_DIR, f'{speaker.lower()}.npy')
    if os.path.exists(emb_path):
        existing = np.load(emb_path)
        # 重み付け結合
        combined = (1 - weight_new) * existing + weight_new * new_emb
        combined = combined / np.linalg.norm(combined) * np.linalg.norm(existing)
    else:
        combined = new_emb

    np.save(emb_path, combined)
    return True, f"{speaker}のエンベディングを更新しました"


def add_subtitles(video_path: str, segments: list, output_path: str, style: str = "pro"):
    """動画に字幕を追加

    Args:
        video_path: 入力動画パス
        segments: セグメントリスト
        output_path: 出力パス
        style: 字幕スタイル ("pro" = プロ風, "simple" = シンプル)
    """
    video = VideoFileClip(video_path)

    # 話者ごとの色（見やすい色を選択）
    SPEAKER_COLORS = {
        # T1
        'faker': '#FF6B6B',    # 赤（コーラルレッド）
        'oner': '#4ECDC4',     # ターコイズ
        'doran': '#FFE66D',    # 黄色
        'peyz': '#95E1D3',     # ミントグリーン
        'keria': '#DDA0DD',    # プラム（紫）
        # GenG
        'chovy': '#FF6B6B',
        'canyon': '#4ECDC4',
        'kiin': '#FFE66D',
        'ruler': '#95E1D3',
        'lehends': '#DDA0DD',
        # HLE
        'zeus': '#FF6B6B',
        'peanut': '#4ECDC4',
        'zeka': '#FFE66D',
        'viper': '#95E1D3',
        'delight': '#DDA0DD',
        # デフォルト
        '???': '#FFFFFF',
    }

    text_clips = []

    if style == "pro":
        # プロ風スタイル: #PlayerName: テキスト（話者別色分け）
        for seg in segments:
            if seg['end'] > video.duration:
                seg['end'] = video.duration
            if seg['start'] >= video.duration:
                continue

            speaker = seg['speaker'].capitalize() if seg['speaker'] else '???'
            # 「ら」を除去（複数話者マーク）
            speaker_clean = speaker.replace('ら', '')
            text = seg.get('text_ja', seg.get('text', ''))

            # 話者の色を取得
            speaker_lower = speaker_clean.lower()
            color = SPEAKER_COLORS.get(speaker_lower, '#FFD700')  # デフォルトはゴールド

            # プロ風フォーマット: #Speaker: テキスト
            display_text = f"#{speaker_clean}: {text}"

            # 字幕クリップ作成（話者別色、アウトライン付き）
            txt = TextClip(
                text=display_text,
                font_size=28,
                font="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                color=color,
                stroke_color="black",
                stroke_width=2,
                method="caption",
                size=(video.w - 60, None)
            )

            # 位置: 画面下部中央
            y_pos = video.h - 80
            txt = txt.with_position(("center", y_pos)).with_start(seg['start']).with_end(seg['end'])
            text_clips.append(txt)

    else:
        # シンプルスタイル（従来）
        for seg in segments:
            if seg['end'] > video.duration:
                seg['end'] = video.duration
            if seg['start'] >= video.duration:
                continue

            color = "lime" if seg['score'] > 0.5 else "yellow" if seg['score'] > 0.4 else "red"
            speaker = seg['speaker'].capitalize() if seg['speaker'] else '???'
            text = seg.get('text_ja', seg.get('text', ''))
            display_text = f"[{speaker}] {text}"

            txt = TextClip(
                text=display_text,
                font_size=22,
                font="/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc",
                color=color,
                bg_color="black",
                margin=(8, 4),
                method="caption",
                size=(video.w - 40, None)
            )
            txt = txt.with_position(("center", video.h - 70)).with_start(seg['start']).with_end(seg['end'])
            text_clips.append(txt)

    final = CompositeVideoClip([video] + text_clips)
    final.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)

    video.close()
    final.close()


def auto_learning(segments: list, audio_path: str):
    """高スコアセグメントから自動学習"""
    print("\n" + "="*50)
    print("🤖 自動学習モード")
    print("="*50)

    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )

    learned_count = 0

    for seg in segments:
        speaker = seg['speaker']
        score = seg['score']

        if not speaker:
            continue

        # スコアに応じた学習
        if score > 0.6:
            # 高スコア: 自動学習（10%の重み）
            success, msg = update_speaker_embedding(
                speaker, audio_path, seg['start'], seg['end'], encoder, weight_new=0.1
            )
            if success:
                learned_count += 1
                print(f"  🟢 {speaker.capitalize()}: {seg.get('text_ja', seg['text'])[:30]}... (自動学習)")
        elif score > 0.5:
            # 中高スコア: 軽い学習（5%の重み）
            success, msg = update_speaker_embedding(
                speaker, audio_path, seg['start'], seg['end'], encoder, weight_new=0.05
            )
            if success:
                learned_count += 1
                print(f"  🟡 {speaker.capitalize()}: {seg.get('text_ja', seg['text'])[:30]}... (軽学習)")

    print(f"\n✅ 自動学習完了: {learned_count}個のセグメントで更新")
    return learned_count


def learn_lol_term(wrong: str, correct: str):
    """LoL用語をカスタム辞書に追加"""
    custom = load_custom_dict()
    custom['terms'][wrong] = correct
    custom['learned_count'] = custom.get('learned_count', 0) + 1
    save_custom_dict(custom)
    print(f"   📚 LoL用語学習: {wrong} → {correct}")


def interactive_learning(segments: list, audio_path: str, team: str, db: dict):
    """対話的に結果を確認・修正して学習"""
    print("\n" + "="*50)
    print("🎓 学習モード")
    print("="*50)
    print("各セグメントの話者を確認してください。")
    print("Enter: 正しい / 選手名を入力: 修正 / s: スキップ / q: 終了")
    print("t: LoL用語修正モード（誤訳を修正して学習）")
    print()

    # チームの選手リスト
    if team and team in db['teams']:
        team_players = db['teams'][team]['players']
        print(f"【{team}の選手】: {', '.join(team_players)}")
    print()

    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )

    learned_count = 0

    for i, seg in enumerate(segments):
        if seg['score'] < 0.3:  # 低スコアは確認
            needs_confirm = True
        elif seg['score'] > 0.6:  # 高スコアは自動承認
            needs_confirm = False
        else:
            needs_confirm = True

        speaker = seg['speaker'].capitalize() if seg['speaker'] else '???'
        conf = "🟢" if seg['score'] > 0.5 else "🟡" if seg['score'] > 0.4 else "🔴"

        print(f"[{i+1}/{len(segments)}] {sec_to_time(seg['start'])} {conf}")
        print(f"  話者: {speaker} ({seg['score']:.2f})")
        print(f"  内容: {seg.get('text_ja', seg['text'])}")

        if not needs_confirm:
            print(f"  → 自動承認（高スコア）")
            # 高スコアのものは自動で学習
            if seg['speaker'] and seg['score'] > 0.6:
                success, msg = update_speaker_embedding(
                    seg['speaker'], audio_path, seg['start'], seg['end'], encoder, weight_new=0.1
                )
                if success:
                    learned_count += 1
            print()
            continue

        response = input(f"  → 確認 (Enter=OK / 選手名 / s=skip / t=用語修正 / q=quit): ").strip().lower()

        if response == 'q':
            break
        elif response == 's':
            print("  → スキップ")
        elif response == 't':
            # LoL用語修正モード
            wrong = input("  → 誤った単語: ").strip()
            correct = input("  → 正しい単語: ").strip()
            if wrong and correct:
                learn_lol_term(wrong, correct)
        elif response == '':
            # 確認OK、学習
            if seg['speaker']:
                success, msg = update_speaker_embedding(
                    seg['speaker'], audio_path, seg['start'], seg['end'], encoder, weight_new=0.2
                )
                if success:
                    learned_count += 1
                    print(f"  → {msg}")
        else:
            # 修正された場合
            corrected_speaker = response
            success, msg = update_speaker_embedding(
                corrected_speaker, audio_path, seg['start'], seg['end'], encoder, weight_new=0.3
            )
            if success:
                learned_count += 1
                print(f"  → {msg}")
            else:
                print(f"  → エラー: {msg}")

        print()

    print(f"\n✅ 学習完了: {learned_count}個のセグメントで更新しました")
    return learned_count


def detect_teamvoice_highlights(url: str, min_score: float = 0.3) -> list:
    """長い動画からチームボイス部分を自動検出"""
    api_key = get_gemini_api_key()
    if not api_key:
        print("❌ GEMINI_API_KEY環境変数を設定してください")
        print("   export GEMINI_API_KEY='your-api-key'")
        return []

    print("=== チームボイス自動検出モード ===")
    print(f"URL: {url}")

    # 1. 動画をダウンロード（全体）
    print("\n1. 動画ダウンロード中...")
    clip_path, title = download_clip(url)
    print(f"   完了: {title}")

    # 2. 音声抽出
    print("\n2. 音声抽出中...")
    audio_path = extract_audio(clip_path)
    print("   完了")

    # 3. 音声認識
    print("\n3. 音声認識中（Whisper）...")
    whisper_segments = transcribe_audio(audio_path, language="ko")
    print(f"   {len(whisper_segments)}セグメント認識")

    # トランスクリプト作成
    lines = []
    for seg in whisper_segments:
        minutes = int(seg['start'] // 60)
        secs = int(seg['start'] % 60)
        lines.append(f"[{minutes:02d}:{secs:02d}] {seg['text']}")
    transcript_text = "\n".join(lines)

    # 4. Geminiでハイライト検出
    print("\n4. チームボイス検出中（Gemini API）...")

    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash')

        # トランスクリプトが長すぎる場合は分割
        max_length = 15000
        if len(transcript_text) > max_length:
            transcript_text = transcript_text[:max_length] + "\n...(truncated)"

        prompt = TEAMVOICE_DETECT_PROMPT.format(transcript=transcript_text)
        response = model.generate_content(prompt)
        result = response.text

        # JSONパース
        highlights = parse_highlight_json(result)

        # フィルタリング
        highlights = [h for h in highlights if h['score'] >= min_score]
        highlights = sorted(highlights, key=lambda h: h['start'])

        print(f"\n   検出されたチームボイス: {len(highlights)}件")
        for i, h in enumerate(highlights):
            start = f"{int(h['start'] // 60):02d}:{int(h['start'] % 60):02d}"
            end = f"{int(h['end'] // 60):02d}:{int(h['end'] % 60):02d}"
            print(f"   {i+1}. [{start} - {end}] {h['title']} (スコア: {h['score']:.2f})")

        return highlights

    except Exception as e:
        print(f"❌ Gemini API エラー: {e}")
        return []


def parse_highlight_json(text: str) -> list:
    """GeminiのレスポンスからハイライトJSONをパース"""
    text = text.strip()

    # コードブロック内のJSONを抽出
    if "```json" in text:
        start = text.index("```json") + 7
        end = text.index("```", start)
        text = text[start:end].strip()
    elif "```" in text:
        start = text.index("```") + 3
        end = text.index("```", start)
        text = text[start:end].strip()

    # 配列を探す
    if "[" in text and "]" in text:
        start = text.index("[")
        end = text.rindex("]") + 1
        text = text[start:end]

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            return []

        highlights = []
        for h in data:
            try:
                highlights.append({
                    'start': float(h.get('start', 0)),
                    'end': float(h.get('end', 0)),
                    'title': h.get('title', 'Unknown'),
                    'description': h.get('description', ''),
                    'type': h.get('type', 'other'),
                    'score': float(h.get('score', 0.5)),
                })
            except (ValueError, KeyError):
                continue

        return highlights

    except json.JSONDecodeError:
        return []


def create_clip_with_speaker(url: str, start_time: str, end_time: str,
                             team: str = None, output_name: str = None,
                             auto_detect_team: bool = True,
                             learn_mode: bool = False,
                             auto_learn_mode: bool = False,
                             use_gemini: bool = False,
                             use_papago: bool = False,
                             separate_audio: bool = False,
                             whisper_model: str = "base",
                             merge_mode: bool = False,
                             subtitle_style: str = "pro") -> str:
    """メイン関数

    Args:
        url: YouTube URL
        start_time: 開始時間
        end_time: 終了時間
        team: チーム指定
        output_name: 出力ファイル名
        auto_detect_team: チーム自動検出
        learn_mode: 対話的学習モード
        auto_learn_mode: 自動学習モード
        use_gemini: Gemini翻訳使用
        use_papago: Papago翻訳使用（韓日特化、推奨）
        separate_audio: 音声分離（Demucs）使用
        whisper_model: Whisperモデルサイズ
    """
    start_sec = time_to_sec(start_time)
    end_sec = time_to_sec(end_time)
    duration = end_sec - start_sec

    print(f"=== 切り抜き動画作成 ===")
    print(f"URL: {url}")
    print(f"区間: {start_time} - {end_time} ({duration}秒)")

    # 設定表示
    settings = []
    if use_papago:
        settings.append("🇰🇷 Papago翻訳")
    elif use_gemini:
        settings.append("🤖 Gemini翻訳")
    else:
        settings.append("📝 googletrans")
    if separate_audio:
        settings.append("🎵 音声分離")
    if whisper_model != "base":
        settings.append(f"🎤 Whisper-{whisper_model}")
    print(f"設定: {' | '.join(settings)}")

    # LoL辞書のステータス表示
    base_corrections = create_correction_dict()
    custom_dict = load_custom_dict()
    print(f"📚 LoL辞書: 基本{len(base_corrections)}件 + カスタム{len(custom_dict.get('terms', {}))}件")

    db = load_database()

    # 1. 指定区間のみダウンロード
    print("\n1. 指定区間ダウンロード中...")
    clip_path, title = download_clip(url, start_sec, end_sec)
    print(f"   完了: {title}")

    # 2. チーム検出
    detected_team = team
    if not team and auto_detect_team:
        print("\n2. チーム自動検出中...")
        detected_team = detect_team_from_title(title)
        if detected_team:
            print(f"   検出: {detected_team}")
        else:
            print("   検出できず、全選手で識別")
    elif team:
        print(f"\n2. チーム指定: {team}")

    # 3. 音声抽出
    print("\n3. 音声抽出中...")
    audio_path = extract_audio(clip_path)
    print("   完了")

    # 3.5. 音声分離（オプション）
    if separate_audio:
        audio_path = separate_vocals(audio_path)

    # 4. 音声認識
    print("\n4. 音声認識中（Whisper）...")
    whisper_segments = transcribe_audio(audio_path, language="ko", model_size=whisper_model)
    print(f"   {len(whisper_segments)}セグメント認識")

    # 5. 話者識別
    print("\n5. 話者識別中...")
    embeddings = load_speaker_embeddings(detected_team, db)
    print(f"   {len(embeddings)}人の選手データで識別")

    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )
    waveform, sr = torchaudio.load(audio_path)

    segments_with_speaker = []
    for seg in whisper_segments:
        speaker, score, confidence = identify_speaker_for_segment(
            waveform, sr, seg['start'], seg['end'], encoder, embeddings,
            text=seg['text'], team=detected_team
        )
        segments_with_speaker.append({
            'start': seg['start'],
            'end': seg['end'],
            'text': seg['text'].strip(),
            'speaker': speaker,
            'score': score,
            'confidence': confidence
        })

    # 6. 日本語翻訳 + LoL用語修正（文脈付き）
    print("\n6. 日本語翻訳 + LoL用語修正中...")
    corrections = get_merged_corrections()

    for i, seg in enumerate(segments_with_speaker):
        # 前後の文脈を取得
        context_before = segments_with_speaker[i-1]['text'] if i > 0 else ""
        context_after = segments_with_speaker[i+1]['text'] if i < len(segments_with_speaker)-1 else ""

        # まず韓国語の音声認識誤りを修正
        text_asr_fixed = correct_korean_asr(seg['text'])
        # 次にLoL用語修正を適用
        text_corrected = correct_text(text_asr_fixed, corrections)

        # 翻訳（文脈付き）
        speaker_name = seg['speaker'].capitalize() if seg['speaker'] else ""
        translated = translate_to_japanese(
            text_corrected,
            speaker=speaker_name,
            use_gemini=use_gemini,
            use_papago=use_papago,
            context_before=context_before,
            context_after=context_after
        )
        # 翻訳後の日本語修正（Papago翻訳ミス対応）
        seg['text_ja'] = correct_japanese_post(translated)
    print("   完了")

    # 7. 全体の文脈を見て翻訳を見直し（Gemini使用時のみ）
    if use_gemini or use_papago:
        print("\n7. 全体の文脈で翻訳レビュー中...")
        segments_with_speaker = review_translations_with_context(
            segments_with_speaker,
            use_gemini=True  # 文脈レビューは常にGeminiを使用
        )
        print("   完了")

    # 会話フローモードの場合、セグメントをマージ
    if merge_mode:
        print("\n   会話フローモード: セグメントを統合中...")
        display_segments = merge_conversation_segments(segments_with_speaker)
        print(f"   {len(segments_with_speaker)}セグメント → {len(display_segments)}セグメントに統合")
    else:
        display_segments = segments_with_speaker

    # 結果表示
    mode_label = "（会話フロー）" if merge_mode else "（日本語）"
    print(f"\n   === 認識結果{mode_label} ===")
    for seg in display_segments:
        if merge_mode:
            # マージモードでは統合数を表示
            count = seg.get('segment_count', 1)
            count_mark = f"[{count}]" if count > 1 else ""
            speaker = seg['speaker'].capitalize() if seg['speaker'] else '???'
            print(f"   {sec_to_time(seg['start'])}-{sec_to_time(seg['end'])} [{speaker}]{count_mark}: {seg['text_ja']}")
        else:
            confidence = seg.get('confidence', 'medium')
            if confidence == 'uncertain':
                conf_icon = "❓"
            elif seg['score'] > 0.5:
                conf_icon = "🟢"
            elif seg['score'] > 0.4:
                conf_icon = "🟡"
            else:
                conf_icon = "🔴"
            speaker = seg['speaker'].capitalize() if seg['speaker'] else '???'
            uncertain_mark = "?" if confidence == 'uncertain' else ""
            print(f"   {sec_to_time(seg['start'])} [{speaker}{uncertain_mark}] {conf_icon}: {seg['text_ja']}")

    # 履歴保存
    history = load_history()
    session = {
        'timestamp': datetime.now().isoformat(),
        'url': url,
        'title': title,
        'start': start_time,
        'end': end_time,
        'team': detected_team,
        'segments': segments_with_speaker,
        'audio_path': audio_path
    }
    history['sessions'].append(session)
    history['last_session'] = session
    save_history(history)

    # 8. 字幕付き動画作成
    print("\n8. 字幕付き動画作成中...")
    if output_name is None:
        team_suffix = f"_{detected_team}" if detected_team else ""
        output_name = f"clip_{start_time.replace(':', '')}_{end_time.replace(':', '')}{team_suffix}.mp4"
    output_path = os.path.join(OUTPUT_DIR, output_name)

    # マージモードの場合は統合されたセグメントを使用
    subtitle_segments = display_segments if merge_mode else segments_with_speaker
    add_subtitles(clip_path, subtitle_segments, output_path, style=subtitle_style)

    size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n=== 完了 ===")
    print(f"出力: {output_path}")
    print(f"サイズ: {size:.2f} MB")

    # 学習モード
    if auto_learn_mode:
        auto_learning(segments_with_speaker, audio_path)
    elif learn_mode:
        interactive_learning(segments_with_speaker, audio_path, detected_team, db)

    # 品質分析と自動改善
    session_quality = analyze_session_quality(segments_with_speaker)
    if session_quality['suggest_improvement'] and detected_team and AUTO_COLLECT_AVAILABLE:
        if AUTO_IMPROVE_CONFIG['enabled']:
            # 自動改善を実行
            auto_improve_in_background(detected_team, session_quality)
        else:
            # 手動改善を推奨
            print(f"\n💡 話者識別の精度が低いセグメントが多いです")
            print(f"   高信頼: {session_quality['high_count']}, "
                  f"中: {session_quality['medium_count']}, "
                  f"低: {session_quality['low_count']}, "
                  f"不明: {session_quality['unknown_count']}")
            print(f"   エンベディング自動改善を推奨:")
            print(f"   python clip_with_speaker.py --improve {detected_team}")

    return output_path


def correct_last_session():
    """直近のセッションを修正して学習"""
    history = load_history()
    if 'last_session' not in history:
        print("学習履歴がありません")
        return

    session = history['last_session']
    print(f"\n直近のセッション: {session['title']}")
    print(f"区間: {session['start']} - {session['end']}")

    db = load_database()
    interactive_learning(
        session['segments'],
        session['audio_path'],
        session['team'],
        db
    )


def check_embedding_quality(team_name: str = None) -> dict:
    """エンベディングの品質をチェック"""
    db = load_database()
    quality_report = {
        'high': [],
        'medium': [],
        'low': [],
        'new': [],
        'missing': [],
    }

    players = db.get('players', {})

    for name, info in players.items():
        # チーム指定がある場合はフィルタリング
        if team_name and info.get('team') != team_name:
            continue

        acc = info.get('accuracy', {})
        level = acc.get('level', 'unknown')
        has_emb = info.get('has_embedding', False)

        if not has_emb:
            quality_report['missing'].append(name)
        elif level == 'high':
            quality_report['high'].append({'name': name, 'score': acc.get('avg', 0)})
        elif level == 'medium':
            quality_report['medium'].append({'name': name, 'score': acc.get('avg', 0)})
        elif level == 'low':
            quality_report['low'].append({'name': name, 'score': acc.get('avg', 0)})
        else:
            quality_report['new'].append(name)

    return quality_report


def improve_embeddings(team_name: str, auto_run: bool = False):
    """エンベディングを自動改善"""
    print(f"\n{'='*60}")
    print(f"🔧 {team_name} エンベディング改善")
    print(f"{'='*60}")

    if not AUTO_COLLECT_AVAILABLE:
        print("❌ auto_collect_voice モジュールが利用できません")
        print("   pip install speechbrain torchaudio yt-dlp whisper を実行してください")
        return

    # 品質チェック
    quality = check_embedding_quality(team_name)

    print("\n📊 現在の品質:")
    print(f"   🟢 高品質: {len(quality['high'])}人")
    for p in quality['high']:
        print(f"      - {p['name']} (avg: {p['score']:.3f})")

    print(f"   🟡 中品質: {len(quality['medium'])}人")
    for p in quality['medium']:
        print(f"      - {p['name']} (avg: {p['score']:.3f})")

    print(f"   🔴 低品質: {len(quality['low'])}人")
    for p in quality['low']:
        print(f"      - {p['name']} (avg: {p['score']:.3f})")

    print(f"   ⚪ 新規: {len(quality['new'])}人")
    for p in quality['new']:
        print(f"      - {p}")

    print(f"   ❌ 未登録: {len(quality['missing'])}人")
    for p in quality['missing']:
        print(f"      - {p}")

    # 改善が必要な選手を特定
    needs_improvement = quality['low'] + quality['new']

    if not needs_improvement:
        print("\n✅ 全ての選手が中〜高品質です。改善は不要です。")
        return

    print(f"\n🎯 改善対象: {len(needs_improvement)}人")

    if not auto_run:
        confirm = input("\n自動収集を開始しますか？ (y/n): ").strip().lower()
        if confirm != 'y':
            print("キャンセルしました")
            return

    # 話者照合方式で収集
    print("\n🚀 チームボイス動画から話者照合で収集開始...")
    results = collect_with_diarization(
        team_name,
        max_videos=5,
        update_embedding=True,
        similarity_threshold=0.45
    )

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"📈 改善結果")
    print(f"{'='*60}")

    improved = [p for p in results if results[p].get('count', 0) >= 3]
    print(f"   改善された選手: {len(improved)}人")
    for p in improved:
        print(f"      - {p}: {results[p]['count']}セグメント (avg: {results[p]['avg_score']:.3f})")

    # 再度品質チェック
    print("\n📊 改善後の品質:")
    new_quality = check_embedding_quality(team_name)
    print(f"   🟢 高品質: {len(new_quality['high'])}人")
    print(f"   🟡 中品質: {len(new_quality['medium'])}人")
    print(f"   🔴 低品質: {len(new_quality['low'])}人")


def analyze_session_quality(segments: list) -> dict:
    """セッションの品質を分析し、改善が必要か判断"""
    total = len(segments)
    if total == 0:
        return {'quality': 'unknown', 'suggest_improvement': False}

    high = sum(1 for s in segments if s.get('confidence') == 'high')
    medium = sum(1 for s in segments if s.get('confidence') == 'medium')
    low = sum(1 for s in segments if s.get('confidence') == 'low')
    unknown = sum(1 for s in segments if (s.get('speaker') or '').startswith('???'))

    high_ratio = high / total
    low_ratio = (low + unknown) / total

    quality = 'high' if high_ratio >= 0.6 else 'medium' if high_ratio >= 0.3 else 'low'
    suggest = low_ratio >= 0.5  # 50%以上が低信頼なら改善を提案

    return {
        'quality': quality,
        'high_count': high,
        'medium_count': medium,
        'low_count': low,
        'unknown_count': unknown,
        'total': total,
        'suggest_improvement': suggest,
    }


def load_auto_improve_log() -> dict:
    """自動改善ログを読み込み"""
    if os.path.exists(AUTO_IMPROVE_LOG_PATH):
        with open(AUTO_IMPROVE_LOG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_improve': {}}


def save_auto_improve_log(log: dict):
    """自動改善ログを保存"""
    os.makedirs(os.path.dirname(AUTO_IMPROVE_LOG_PATH), exist_ok=True)
    with open(AUTO_IMPROVE_LOG_PATH, 'w', encoding='utf-8') as f:
        json.dump(log, f, ensure_ascii=False, indent=2)


def can_auto_improve(team_name: str) -> bool:
    """クールダウン期間内かチェック"""
    log = load_auto_improve_log()
    last_time = log.get('last_improve', {}).get(team_name, 0)
    elapsed = datetime.now().timestamp() - last_time
    return elapsed >= AUTO_IMPROVE_CONFIG['cooldown']


def auto_improve_in_background(team_name: str, session_quality: dict):
    """バックグラウンドで自動改善を実行"""
    if not AUTO_IMPROVE_CONFIG['enabled']:
        return

    if not AUTO_COLLECT_AVAILABLE:
        return

    if not can_auto_improve(team_name):
        print(f"   ⏳ {team_name}の自動改善はクールダウン中です")
        return

    # ログ更新
    log = load_auto_improve_log()
    if 'last_improve' not in log:
        log['last_improve'] = {}
    log['last_improve'][team_name] = datetime.now().timestamp()
    save_auto_improve_log(log)

    print(f"\n🔄 自動改善開始: {team_name}")
    print(f"   品質: 高{session_quality['high_count']}, "
          f"中{session_quality['medium_count']}, "
          f"低{session_quality['low_count']}, "
          f"不明{session_quality['unknown_count']}")

    # バックグラウンドで改善を実行
    def run_improvement():
        try:
            # 収集実行（最大3動画）
            results = collect_with_diarization(team_name, max_videos=3)

            if results:
                print(f"\n✅ {team_name}の自動改善完了")
                for player, data in results.items():
                    print(f"   {player}: {data['count']}セグメント収集")
            else:
                print(f"\n⚠️ {team_name}の自動改善: 新しいセグメントなし")
        except Exception as e:
            print(f"\n❌ 自動改善エラー: {e}")

    thread = threading.Thread(target=run_improvement, daemon=True)
    thread.start()
    print("   💡 バックグラウンドで改善中... 次の処理に進めます")


def process_detected_highlights(url: str, highlights: list, use_gemini: bool = False,
                                use_papago: bool = False, auto_learn: bool = False):
    """検出されたハイライトを処理"""
    if not highlights:
        print("処理するハイライトがありません")
        return

    print(f"\n=== {len(highlights)}件のハイライトを処理 ===")

    for i, h in enumerate(highlights):
        start_time = f"{int(h['start'] // 60)}:{int(h['start'] % 60):02d}"
        end_time = f"{int(h['end'] // 60)}:{int(h['end'] % 60):02d}"

        print(f"\n[{i+1}/{len(highlights)}] {h['title']}")
        print(f"   区間: {start_time} - {end_time}")

        # 安全なファイル名を生成
        safe_title = "".join(c for c in h['title'][:20] if c.isalnum() or c in "_ -あ-んア-ン一-龥").strip()
        if not safe_title:
            safe_title = f"clip_{i+1}"
        output_name = f"highlight_{i+1:02d}_{safe_title}.mp4"

        create_clip_with_speaker(
            url=url,
            start_time=start_time,
            end_time=end_time,
            output_name=output_name,
            use_gemini=use_gemini,
            use_papago=use_papago,
            auto_learn_mode=auto_learn
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='YouTube切り抜き + 話者識別 + 自動学習 + Gemini翻訳')
    parser.add_argument('url', nargs='?', help='YouTube URL')
    parser.add_argument('start', nargs='?', help='開始時間')
    parser.add_argument('end', nargs='?', help='終了時間')
    parser.add_argument('--team', '-t', help='チーム指定')
    parser.add_argument('--output', '-o', help='出力ファイル名')
    parser.add_argument('--gemini', '-g', action='store_true', help='Gemini APIで高精度翻訳（文脈付き）')
    parser.add_argument('--papago', '-p', action='store_true', help='Papago翻訳（韓日特化、推奨）')
    parser.add_argument('--merge', '-m', action='store_true', help='会話フローモード（セグメントを統合して自然な字幕に）')
    parser.add_argument('--style', default='pro', choices=['pro', 'simple'], help='字幕スタイル（pro=プロ風黄色, simple=シンプル）')
    parser.add_argument('--detect', '-d', action='store_true', help='チームボイス自動検出モード')
    parser.add_argument('--learn', '-l', action='store_true', help='対話的学習モード')
    parser.add_argument('--auto-learn', '-a', action='store_true', help='自動学習モード（高スコアのみ）')
    parser.add_argument('--correct', '-c', action='store_true', help='直近の結果を修正')
    parser.add_argument('--improve', '-i', help='指定チームのエンベディングを自動改善（T1, GenG, HLE, DK, KT）')
    parser.add_argument('--no-auto-improve', action='store_true', help='自動品質改善を無効化')
    parser.add_argument('--quality', '-q', action='store_true', help='エンベディング品質をチェック')
    parser.add_argument('--backup', action='store_true', help='エンベディングをバックアップ')
    parser.add_argument('--restore', nargs='?', const='latest', help='バックアップから復元')
    parser.add_argument('--list-backups', action='store_true', help='バックアップ一覧')
    parser.add_argument('--no-auto-team', action='store_true', help='チーム自動検出を無効化')
    parser.add_argument('--min-score', type=float, default=0.3, help='検出モードの最小スコア')

    # 精度向上オプション
    parser.add_argument('--separate', '-s', action='store_true',
                        help='音声分離（Demucs）でゲーム音を除去')
    parser.add_argument('--whisper-model', '-w', default='medium',
                        choices=['tiny', 'base', 'small', 'medium', 'large'],
                        help='Whisperモデルサイズ（デフォルト: medium、大きいほど高精度だが遅い）')
    parser.add_argument('--high-quality', '-hq', action='store_true',
                        help='高品質モード（--gemini --separate --whisper-model medium を有効化）')

    # 翻訳学習オプション
    parser.add_argument('--add-fix', nargs=2, metavar=('WRONG', 'CORRECT'),
                        help='翻訳修正を学習（例: --add-fix "悟空" "ゾーニャ"）')
    parser.add_argument('--list-fixes', action='store_true',
                        help='学習済み翻訳修正の一覧')
    parser.add_argument('--remove-fix', metavar='WRONG',
                        help='学習済み翻訳修正を削除')

    args = parser.parse_args()

    # 高品質モードの設定
    if args.high_quality:
        args.gemini = True
        args.separate = True
        args.whisper_model = 'medium'

    # 自動改善の無効化
    if args.no_auto_improve:
        AUTO_IMPROVE_CONFIG['enabled'] = False

    # 翻訳学習コマンド
    if args.add_fix:
        from lol_dictionary import save_learned_correction
        wrong, correct = args.add_fix
        save_learned_correction(wrong, correct, context="manual")
        sys.exit(0)
    elif args.list_fixes:
        from lol_dictionary import list_learned_corrections
        fixes = list_learned_corrections()
        if not fixes:
            print("\n📚 学習済み翻訳修正はありません")
        else:
            print(f"\n📚 学習済み翻訳修正 ({len(fixes)}件)")
            print("=" * 60)
            for i, fix in enumerate(fixes):
                print(f"  [{i+1}] 「{fix['wrong']}」→「{fix['correct']}」")
                if fix.get('context'):
                    print(f"       文脈: {fix['context']}")
                print(f"       日時: {fix['timestamp'][:16]}")
        sys.exit(0)
    elif args.remove_fix:
        from lol_dictionary import remove_learned_correction
        remove_learned_correction(args.remove_fix)
        sys.exit(0)

    if args.list_backups:
        if not AUTO_COLLECT_AVAILABLE:
            print("❌ auto_collect_voice モジュールが利用できません")
        else:
            backups = list_backups()
            if not backups:
                print("\n💾 バックアップはありません")
            else:
                print(f"\n💾 バックアップ一覧 ({len(backups)}件)")
                print("=" * 60)
                for i, b in enumerate(backups):
                    print(f"  [{i+1}] {b['name']}")
                    print(f"      日時: {b['timestamp']}")
                    print(f"      理由: {b['reason']}")
                    print(f"      ファイル: {len(b.get('files', []))}個")
    elif args.backup:
        if not AUTO_COLLECT_AVAILABLE:
            print("❌ auto_collect_voice モジュールが利用できません")
        else:
            print("\n💾 手動バックアップ作成中...")
            create_backup(reason="manual")
            print("✅ バックアップ完了")
    elif args.restore:
        if not AUTO_COLLECT_AVAILABLE:
            print("❌ auto_collect_voice モジュールが利用できません")
        else:
            backup_name = None if args.restore == 'latest' else args.restore
            print(f"\n🔄 バックアップから復元中...")
            restore_backup(backup_name)
    elif args.correct:
        correct_last_session()
    elif args.quality:
        # 品質チェックモード
        team = args.team or args.improve
        quality = check_embedding_quality(team)
        print(f"\n{'='*60}")
        print(f"📊 エンベディング品質レポート" + (f" ({team})" if team else ""))
        print(f"{'='*60}")
        print(f"   🟢 高品質: {len(quality['high'])}人")
        for p in quality['high']:
            print(f"      - {p['name']} (avg: {p['score']:.3f})")
        print(f"   🟡 中品質: {len(quality['medium'])}人")
        for p in quality['medium']:
            print(f"      - {p['name']} (avg: {p['score']:.3f})")
        print(f"   🔴 低品質: {len(quality['low'])}人")
        for p in quality['low']:
            print(f"      - {p['name']} (avg: {p['score']:.3f})")
        print(f"   ⚪ 新規: {len(quality['new'])}人")
        for p in quality['new']:
            print(f"      - {p}")
        if quality['low'] or quality['new']:
            print(f"\n💡 改善が必要な選手がいます。以下のコマンドで自動改善:")
            team_arg = f" --team {team}" if team else ""
            print(f"   python clip_with_speaker.py --improve{team_arg}")
    elif args.improve:
        # エンベディング自動改善モード
        improve_embeddings(args.improve)
    elif args.detect and args.url:
        # チームボイス自動検出モード
        highlights = detect_teamvoice_highlights(args.url, min_score=args.min_score)
        if highlights:
            print("\n処理を開始しますか？ (y/n): ", end="")
            try:
                response = input().strip().lower()
                if response == 'y':
                    process_detected_highlights(
                        args.url, highlights,
                        use_gemini=args.gemini,
                        use_papago=args.papago,
                        auto_learn=args.auto_learn
                    )
            except EOFError:
                # 非対話環境では全処理
                process_detected_highlights(
                    args.url, highlights,
                    use_gemini=args.gemini,
                    use_papago=args.papago,
                    auto_learn=args.auto_learn
                )
    elif args.url and args.start and args.end:
        create_clip_with_speaker(
            url=args.url,
            start_time=args.start,
            end_time=args.end,
            team=args.team,
            output_name=args.output,
            auto_detect_team=not args.no_auto_team,
            learn_mode=args.learn,
            auto_learn_mode=args.auto_learn,
            use_gemini=args.gemini,
            use_papago=args.papago,
            separate_audio=args.separate,
            whisper_model=args.whisper_model,
            merge_mode=args.merge,
            subtitle_style=args.style
        )
    else:
        parser.print_help()
        print("\n使用例:")
        print("  # 通常処理（指定区間を切り抜き）")
        print("  python clip_with_speaker.py 'https://youtube.com/...' 12:33 13:06")
        print()
        print("  # 高品質モード（Gemini翻訳 + 音声分離 + 中型Whisper）")
        print("  python clip_with_speaker.py 'https://youtube.com/...' 12:33 13:06 --high-quality")
        print()
        print("  # 個別オプション")
        print("  python clip_with_speaker.py 'https://youtube.com/...' 12:33 13:06 --gemini --separate -w medium")
        print()
        print("  # チームボイス自動検出（長い動画から盛り上がり部分を検出）")
        print("  python clip_with_speaker.py 'https://youtube.com/...' --detect")
        print()
        print("  # 学習モード")
        print("  python clip_with_speaker.py 'https://youtube.com/...' 12:33 13:06 --learn")
        print()
        print("  # エンベディング品質チェック")
        print("  python clip_with_speaker.py --quality")
        print("  python clip_with_speaker.py --quality --team T1")
        print()
        print("  # エンベディング自動改善（チームボイス動画から話者照合で収集）")
        print("  python clip_with_speaker.py --improve T1")
