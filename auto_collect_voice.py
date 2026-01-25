#!/usr/bin/env python3
"""
選手の音声を自動収集してエンベディングを更新するシステム

使用方法:
    # 特定の選手の音声を収集（インタビュー動画から - 非推奨）
    python auto_collect_voice.py Faker

    # チームボイス動画から自動収集（推奨）
    python auto_collect_voice.py --team-voice-auto T1

    # 特定選手のチームボイスから収集
    python auto_collect_voice.py --team-voice-auto T1 --player Faker

    # チーム全員の音声を収集
    python auto_collect_voice.py --team T1

    # 全選手の音声を収集
    python auto_collect_voice.py --all

    # 収集のみ（エンベディング更新なし）
    python auto_collect_voice.py Faker --collect-only
"""

import os
import sys
import json
import argparse
import subprocess
import numpy as np
import torchaudio
import torch
import whisper
from datetime import datetime
from pathlib import Path
import yt_dlp
from speechbrain.inference.speaker import EncoderClassifier

# 設定
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDINGS_DIR = os.path.join(BASE_DIR, 'data/speaker_embeddings_v2')
BACKUP_DIR = os.path.join(BASE_DIR, 'data/embeddings_backup')
CACHE_DIR = os.path.join(BASE_DIR, 'data/speechbrain_cache')
COLLECT_DIR = os.path.join(BASE_DIR, 'downloads/collected_voices')
DB_PATH = os.path.join(BASE_DIR, 'data/speaker_database.json')
BACKUP_HISTORY_PATH = os.path.join(BASE_DIR, 'data/backup_history.json')

# 選手の検索キーワード（韓国語名、英語名、ニックネーム）
PLAYER_SEARCH_KEYWORDS = {
    # T1
    'faker': ['Faker interview', 'T1 Faker', '페이커 인터뷰', 'Faker voice'],
    'keria': ['Keria interview', 'T1 Keria', '케리아 인터뷰'],
    'oner': ['Oner interview', 'T1 Oner', '오너 인터뷰'],
    'peyz': ['Peyz interview', 'T1 Peyz', '페이즈 인터뷰'],
    'doran': ['Doran interview', 'T1 Doran', '도란 인터뷰'],

    # GenG
    'chovy': ['Chovy interview', 'GenG Chovy', '쵸비 인터뷰'],
    'canyon': ['Canyon interview', 'GenG Canyon', '캐니언 인터뷰'],
    'ruler': ['Ruler interview', 'GenG Ruler', '룰러 인터뷰'],
    'kiin': ['Kiin interview', 'GenG Kiin', '기인 인터뷰'],
    'duro': ['Duro interview', 'GenG Duro', '듀로 인터뷰'],

    # HLE
    'zeus': ['Zeus interview', 'HLE Zeus', '제우스 인터뷰', 'T1 Zeus'],
    'peanut': ['Peanut interview', 'HLE Peanut', '피넛 인터뷰'],
    'zeka': ['Zeka interview', 'HLE Zeka', '제카 인터뷰'],
    'gumayusi': ['Gumayusi interview', 'HLE Gumayusi', '구마유시 인터뷰', 'T1 Gumayusi'],
    'viper': ['Viper interview', 'HLE Viper', '바이퍼 인터뷰'],
    'delight': ['Delight interview', 'HLE Delight', '딜라이트 인터뷰'],

    # DK
    'showmaker': ['ShowMaker interview', 'DK ShowMaker', '쇼메이커 인터뷰'],
    'lucid': ['Lucid interview', 'DK Lucid', '루시드 인터뷰'],
    'siwoo': ['Siwoo interview', 'DK Siwoo', '시우 인터뷰'],

    # KT
    'bdd': ['Bdd interview', 'KT Bdd', '비디디 인터뷰'],
    'cuzz': ['Cuzz interview', 'KT Cuzz', '커즈 인터뷰'],
    'aiming': ['Aiming interview', 'KT Aiming', '에이밍 인터뷰'],
}

# チームボイス動画の検索キーワード
TEAM_VOICE_KEYWORDS = {
    'T1': ['T1 team voice', 'T1 comms', 'T1 팀 보이스', 'T1 voice comms', 'T1 LCK 팀 보이스'],
    'GenG': ['GenG team voice', 'GenG comms', 'GenG 팀 보이스', 'Gen.G LCK 팀 보이스'],
    'HLE': ['HLE team voice', 'Hanwha team voice', 'HLE comms', 'HLE LCK 팀 보이스'],
    'DK': ['DK team voice', 'Dplus KIA comms', 'DK 팀 보이스', 'DK LCK 팀 보이스'],
    'KT': ['KT team voice', 'KT Rolster comms', 'KT 팀 보이스', 'KT LCK 팀 보이스'],
}

# 選手名の韓国語マッピング
PLAYER_NAME_KOREAN = {
    # T1
    'faker': ['페이커', 'Faker', 'faker'],
    'keria': ['케리아', 'Keria', 'keria'],
    'oner': ['오너', 'Oner', 'oner'],
    'peyz': ['페이즈', 'Peyz', 'peyz'],
    'doran': ['도란', 'Doran', 'doran'],
    # GenG
    'chovy': ['쵸비', 'Chovy', 'chovy'],
    'canyon': ['캐년', '캐니언', 'Canyon', 'canyon'],
    'ruler': ['룰러', 'Ruler', 'ruler'],
    'kiin': ['기인', 'Kiin', 'kiin'],
    'duro': ['듀로', 'Duro', 'duro'],
    'lehends': ['레헨즈', 'Lehends', 'lehends'],
    # HLE
    'zeus': ['제우스', 'Zeus', 'zeus'],
    'peanut': ['피넛', 'Peanut', 'peanut'],
    'zeka': ['제카', 'Zeka', 'zeka'],
    'gumayusi': ['구마유시', 'Gumayusi', 'gumayusi'],
    'viper': ['바이퍼', 'Viper', 'viper'],
    'delight': ['딜라이트', 'Delight', 'delight'],
    'kanavi': ['카나비', 'Kanavi', 'kanavi'],
    # DK
    'showmaker': ['쇼메이커', 'ShowMaker', 'showmaker', 'Showmaker'],
    'lucid': ['루시드', 'Lucid', 'lucid'],
    'siwoo': ['시우', 'Siwoo', 'siwoo'],
    'smash': ['스매쉬', 'Smash', 'smash'],
    'career': ['커리어', 'Career', 'career'],
    'vicla': ['빅라', 'VicLa', 'vicla'],
    # KT
    'bdd': ['비디디', 'Bdd', 'bdd', 'BDD'],
    'cuzz': ['커즈', 'Cuzz', 'cuzz'],
    'aiming': ['에이밍', 'Aiming', 'aiming'],
    'perfect': ['퍼펙트', 'PerfecT', 'perfect', 'Perfect'],
    'ghost': ['고스트', 'Ghost', 'ghost'],
}

import re

# pyannote-audioの話者ダイアライゼーション（オプション）
try:
    from pyannote.audio import Pipeline
    PYANNOTE_AVAILABLE = True
except ImportError:
    PYANNOTE_AVAILABLE = False


def load_database():
    """選手データベースを読み込み"""
    with open(DB_PATH, 'r') as f:
        return json.load(f)


def save_database(db):
    """選手データベースを保存"""
    db['updated'] = datetime.now().isoformat()
    with open(DB_PATH, 'w') as f:
        json.dump(db, f, indent=2, ensure_ascii=False)


def load_backup_history() -> dict:
    """バックアップ履歴を読み込み"""
    if os.path.exists(BACKUP_HISTORY_PATH):
        with open(BACKUP_HISTORY_PATH, 'r') as f:
            return json.load(f)
    return {'backups': [], 'max_backups': 10}


def save_backup_history(history: dict):
    """バックアップ履歴を保存"""
    with open(BACKUP_HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


def create_backup(reason: str = "manual") -> str:
    """エンベディングのバックアップを作成"""
    os.makedirs(BACKUP_DIR, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"backup_{timestamp}"
    backup_path = os.path.join(BACKUP_DIR, backup_name)

    # バックアップディレクトリ作成
    os.makedirs(backup_path, exist_ok=True)

    # エンベディングファイルをコピー
    import shutil
    backed_up = []
    for f in os.listdir(EMBEDDINGS_DIR):
        if f.endswith('.npy'):
            src = os.path.join(EMBEDDINGS_DIR, f)
            dst = os.path.join(backup_path, f)
            shutil.copy2(src, dst)
            backed_up.append(f)

    # データベースもバックアップ
    if os.path.exists(DB_PATH):
        shutil.copy2(DB_PATH, os.path.join(backup_path, 'speaker_database.json'))

    # 履歴に追加
    history = load_backup_history()
    history['backups'].append({
        'name': backup_name,
        'path': backup_path,
        'timestamp': datetime.now().isoformat(),
        'reason': reason,
        'files': backed_up,
    })

    # 古いバックアップを削除（最大数を超えた場合）
    max_backups = history.get('max_backups', 10)
    while len(history['backups']) > max_backups:
        old_backup = history['backups'].pop(0)
        old_path = old_backup['path']
        if os.path.exists(old_path):
            shutil.rmtree(old_path)
            print(f"   🗑️ 古いバックアップを削除: {old_backup['name']}")

    save_backup_history(history)

    print(f"   💾 バックアップ作成: {backup_name} ({len(backed_up)}ファイル)")
    return backup_path


def list_backups() -> list:
    """利用可能なバックアップ一覧"""
    history = load_backup_history()
    return history.get('backups', [])


def restore_backup(backup_name: str = None) -> bool:
    """バックアップからエンベディングを復元"""
    history = load_backup_history()
    backups = history.get('backups', [])

    if not backups:
        print("❌ バックアップがありません")
        return False

    # バックアップ名が指定されていない場合は最新を使用
    if backup_name is None:
        backup_info = backups[-1]
    else:
        backup_info = None
        for b in backups:
            if b['name'] == backup_name:
                backup_info = b
                break
        if not backup_info:
            print(f"❌ バックアップ '{backup_name}' が見つかりません")
            return False

    backup_path = backup_info['path']
    if not os.path.exists(backup_path):
        print(f"❌ バックアップディレクトリが存在しません: {backup_path}")
        return False

    import shutil

    # 現在の状態をバックアップ（復元前）
    create_backup(reason="pre_restore")

    # エンベディングを復元
    restored = []
    for f in os.listdir(backup_path):
        if f.endswith('.npy'):
            src = os.path.join(backup_path, f)
            dst = os.path.join(EMBEDDINGS_DIR, f)
            shutil.copy2(src, dst)
            restored.append(f)

    # データベースを復元
    db_backup = os.path.join(backup_path, 'speaker_database.json')
    if os.path.exists(db_backup):
        shutil.copy2(db_backup, DB_PATH)

    print(f"✅ 復元完了: {backup_info['name']}")
    print(f"   復元ファイル: {len(restored)}個")
    print(f"   日時: {backup_info['timestamp']}")
    print(f"   理由: {backup_info['reason']}")

    return True


def restore_player_embedding(player_name: str, backup_name: str = None) -> bool:
    """特定選手のエンベディングのみ復元"""
    history = load_backup_history()
    backups = history.get('backups', [])

    if not backups:
        print("❌ バックアップがありません")
        return False

    # バックアップを選択
    if backup_name is None:
        backup_info = backups[-1]
    else:
        backup_info = None
        for b in backups:
            if b['name'] == backup_name:
                backup_info = b
                break
        if not backup_info:
            print(f"❌ バックアップ '{backup_name}' が見つかりません")
            return False

    backup_path = backup_info['path']
    emb_file = f"{player_name.lower()}.npy"
    src = os.path.join(backup_path, emb_file)
    dst = os.path.join(EMBEDDINGS_DIR, emb_file)

    if not os.path.exists(src):
        print(f"❌ バックアップに {player_name} のエンベディングがありません")
        return False

    import shutil
    shutil.copy2(src, dst)

    print(f"✅ {player_name} のエンベディングを復元しました")
    print(f"   バックアップ: {backup_info['name']} ({backup_info['timestamp']})")

    return True


def download_with_subtitles(url: str, output_dir: str) -> tuple:
    """動画と字幕をダウンロード"""
    os.makedirs(output_dir, exist_ok=True)

    common_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
    }

    try:
        # 動画情報取得
        with yt_dlp.YoutubeDL(common_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_id = info.get('id')
            duration = info.get('duration', 0)

            if duration > 1800:  # 30分以上はスキップ
                print(f"   ⚠️ 動画が長すぎます ({duration}秒)")
                return None, None

        audio_path = os.path.join(output_dir, f"{video_id}.wav")
        sub_path = os.path.join(output_dir, f"{video_id}.ko.vtt")

        # 既にダウンロード済みならスキップ
        if os.path.exists(audio_path) and os.path.exists(sub_path):
            print(f"   ♻️ キャッシュ使用: {video_id}")
            return audio_path, sub_path

        # 字幕付きでダウンロード
        ydl_opts = {
            **common_opts,
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(output_dir, f"{video_id}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
            'writesubtitles': True,
            'writeautomaticsub': True,
            'subtitleslangs': ['ko', 'ko-KR', 'en'],
            'subtitlesformat': 'vtt',
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        # 字幕ファイルを探す
        for ext in ['.ko.vtt', '.ko-KR.vtt', '.en.vtt', '.vtt']:
            possible_sub = os.path.join(output_dir, f"{video_id}{ext}")
            if os.path.exists(possible_sub):
                sub_path = possible_sub
                break
        else:
            sub_path = None

        return audio_path, sub_path

    except Exception as e:
        print(f"   ダウンロードエラー: {e}")
        return None, None


def parse_vtt_for_players(vtt_path: str) -> dict:
    """VTT字幕を解析して選手ごとのセグメントを抽出"""
    player_segments = {}

    if not vtt_path or not os.path.exists(vtt_path):
        return player_segments

    try:
        with open(vtt_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # VTTをパース
        # 形式: 00:00:00.000 --> 00:00:03.000
        #       [選手名] テキスト
        time_pattern = r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2}\.\d{3})'

        lines = content.split('\n')
        current_start = None
        current_end = None

        for i, line in enumerate(lines):
            # タイムスタンプ行を検出
            time_match = re.search(time_pattern, line)
            if time_match:
                current_start = parse_timestamp(time_match.group(1))
                current_end = parse_timestamp(time_match.group(2))
                continue

            if current_start is None:
                continue

            # 選手名を検出
            # パターン: [Faker], 페이커:, Faker:, 【Faker】 など
            for player_lower, aliases in PLAYER_NAME_KOREAN.items():
                for alias in aliases:
                    patterns = [
                        rf'\[{re.escape(alias)}\]',
                        rf'【{re.escape(alias)}】',
                        rf'{re.escape(alias)}\s*:',
                        rf'^{re.escape(alias)}\s*$',
                    ]
                    for pattern in patterns:
                        if re.search(pattern, line, re.IGNORECASE):
                            if player_lower not in player_segments:
                                player_segments[player_lower] = []
                            player_segments[player_lower].append({
                                'start': current_start,
                                'end': current_end,
                                'text': line.strip(),
                            })
                            break

        # 重複を除去してマージ
        for player in player_segments:
            player_segments[player] = merge_segments(player_segments[player])

        return player_segments

    except Exception as e:
        print(f"   字幕解析エラー: {e}")
        return {}


def parse_timestamp(ts: str) -> float:
    """タイムスタンプを秒に変換"""
    parts = ts.replace(',', '.').split(':')
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    return 0


def merge_segments(segments: list, gap: float = 1.0) -> list:
    """近接するセグメントをマージ"""
    if not segments:
        return []

    sorted_segs = sorted(segments, key=lambda x: x['start'])
    merged = [sorted_segs[0].copy()]

    for seg in sorted_segs[1:]:
        if seg['start'] - merged[-1]['end'] < gap:
            merged[-1]['end'] = max(merged[-1]['end'], seg['end'])
        else:
            merged.append(seg.copy())

    return merged


def load_existing_embeddings(team_name: str = None) -> dict:
    """既存のエンベディングを読み込み"""
    embeddings = {}
    db = load_database()

    for player_name, info in db.get('players', {}).items():
        # チーム指定がある場合はフィルタリング
        if team_name and info.get('team') != team_name:
            continue

        emb_file = info.get('embedding_file')
        if emb_file:
            emb_path = os.path.join(EMBEDDINGS_DIR, emb_file)
            if os.path.exists(emb_path):
                emb = np.load(emb_path)
                if len(emb.shape) == 1 and emb.shape[0] == 192:
                    embeddings[player_name.lower()] = {
                        'embedding': emb,
                        'name': player_name,
                        'team': info.get('team'),
                    }
    return embeddings


def identify_speaker(embedding: np.ndarray, known_embeddings: dict,
                     threshold: float = 0.4) -> tuple:
    """エンベディングを既知の選手と照合"""
    best_match = None
    best_score = -1

    for player, info in known_embeddings.items():
        known_emb = info['embedding']
        # コサイン類似度
        score = np.dot(embedding, known_emb) / (
            np.linalg.norm(embedding) * np.linalg.norm(known_emb)
        )
        if score > best_score:
            best_score = score
            best_match = info['name']

    if best_score >= threshold:
        return best_match, best_score
    return None, best_score


def collect_with_diarization(team_name: str, target_player: str = None,
                             max_videos: int = 3, update_embedding: bool = True,
                             similarity_threshold: float = 0.45) -> dict:
    """話者ダイアライゼーション + 既存エンベディング照合による収集（推奨）"""
    print(f"\n{'='*60}")
    print(f"🎯 {team_name} チームボイスから話者照合で収集")
    print(f"{'='*60}")

    if target_player:
        print(f"   対象選手: {target_player}")
    print(f"   類似度閾値: {similarity_threshold}")

    keywords = TEAM_VOICE_KEYWORDS.get(team_name, [f"{team_name} team voice LCK"])
    team_dir = os.path.join(COLLECT_DIR, f"diarize_{team_name.lower()}")
    os.makedirs(team_dir, exist_ok=True)

    # エンコーダー初期化
    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )

    # 既存エンベディングを読み込み
    print("\n📂 既存エンベディングを読み込み中...")
    known_embeddings = load_existing_embeddings(team_name)
    print(f"   {len(known_embeddings)}選手のエンベディングを読み込み")

    if not known_embeddings:
        print("   ⚠️ 既存のエンベディングがありません")
        return {}

    # 収集結果
    collected = {}
    processed_videos = []

    for keyword in keywords[:2]:
        print(f"\n🔍 検索: {keyword}")
        videos = search_youtube(keyword, max_results=max_videos)

        for video in videos:
            if video['id'] in processed_videos:
                continue

            print(f"\n📹 {video['title'][:60]}...")
            print(f"   URL: {video['url']}")

            # 音声ダウンロード
            audio_path = download_audio(video['url'], team_dir)
            if not audio_path:
                continue

            processed_videos.append(video['id'])

            # Whisperで発話区間検出
            print("   🎙️ 発話区間検出中...")
            segments = detect_speech_segments(audio_path, min_speech_duration=2.0)
            print(f"   検出: {len(segments)}セグメント")

            # 各セグメントを既知選手と照合
            print("   🔍 話者照合中...")
            matched_count = 0

            for seg in segments[:30]:  # 最大30セグメント
                emb = extract_embedding(audio_path, seg['start'], seg['end'], encoder)
                if emb is None:
                    continue

                # 既知選手と照合
                matched_player, score = identify_speaker(
                    emb, known_embeddings, threshold=similarity_threshold
                )

                if matched_player:
                    player_lower = matched_player.lower()

                    # 対象選手のフィルタリング
                    if target_player and player_lower != target_player.lower():
                        continue

                    if player_lower not in collected:
                        collected[player_lower] = []

                    collected[player_lower].append({
                        'embedding': emb,
                        'video_id': video['id'],
                        'start': seg['start'],
                        'end': seg['end'],
                        'score': score,
                        'text': seg.get('text', ''),
                    })
                    matched_count += 1

            print(f"   ✅ {matched_count}セグメントを照合")

            # 選手ごとの結果
            for player, segs in collected.items():
                recent = [s for s in segs if s['video_id'] == video['id']]
                if recent:
                    avg_score = sum(s['score'] for s in recent) / len(recent)
                    print(f"      {player}: {len(recent)}セグメント (平均スコア: {avg_score:.3f})")

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"📊 収集結果サマリー")
    print(f"{'='*60}")

    results = {}
    for player, segments in collected.items():
        count = len(segments)
        avg_score = sum(s['score'] for s in segments) / count if count > 0 else 0
        results[player] = {'count': count, 'avg_score': avg_score}
        print(f"   {player}: {count}セグメント (平均スコア: {avg_score:.3f})")

        # 高スコアセグメントのみでエンベディング更新
        if update_embedding and count >= 3:
            # スコアでソートして上位を使用
            high_quality = sorted(segments, key=lambda x: x['score'], reverse=True)
            top_segments = high_quality[:min(10, count)]
            min_score = min(s['score'] for s in top_segments)

            if min_score >= similarity_threshold:
                print(f"   🔄 {player}のエンベディング更新中...")
                print(f"      使用セグメント: {len(top_segments)} (スコア {min_score:.3f}〜{top_segments[0]['score']:.3f})")

                embeddings = [seg['embedding'] for seg in top_segments]
                success = update_player_embedding(player.capitalize(), embeddings, weight_new=0.15)

                if success:
                    print(f"   ✅ {player}のエンベディングを更新しました")

                    # データベース更新
                    db = load_database()
                    player_cap = player.capitalize()
                    if player_cap in db.get('players', {}):
                        old_acc = db['players'][player_cap].get('accuracy', {})
                        db['players'][player_cap]['accuracy'] = {
                            'max': float(max(old_acc.get('max', 0), top_segments[0]['score'])),
                            'avg': float((old_acc.get('avg', 0) + avg_score) / 2),
                            'level': 'high' if avg_score >= 0.5 else 'medium' if avg_score >= 0.35 else 'low',
                            'source': 'diarization_matched',
                            'collected_segments': count,
                        }
                        save_database(db)
            else:
                print(f"   ⚠️ {player}: スコアが低いため更新をスキップ")

    if not results:
        print("   ⚠️ 選手音声を収集できませんでした")

    return results


def collect_from_team_voice(team_name: str, target_player: str = None,
                            max_videos: int = 5, update_embedding: bool = True) -> dict:
    """チームボイス動画から選手音声を自動収集（推奨方式）"""
    print(f"\n{'='*60}")
    print(f"🎮 {team_name} チームボイス動画から自動収集")
    print(f"{'='*60}")

    if target_player:
        print(f"   対象選手: {target_player}")

    keywords = TEAM_VOICE_KEYWORDS.get(team_name, [f"{team_name} team voice LCK"])
    team_dir = os.path.join(COLLECT_DIR, f"team_voice_{team_name.lower()}")
    os.makedirs(team_dir, exist_ok=True)

    # エンコーダー初期化
    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )

    # 選手ごとの収集結果
    collected = {}
    processed_videos = []

    for keyword in keywords[:2]:  # 検索キーワードは2つまで
        print(f"\n🔍 検索: {keyword}")
        videos = search_youtube(keyword, max_results=max_videos)

        for video in videos:
            if video['id'] in processed_videos:
                continue

            print(f"\n📹 {video['title'][:60]}...")
            print(f"   URL: {video['url']}")

            # 音声と字幕をダウンロード
            print("   📥 ダウンロード中...")
            audio_path, sub_path = download_with_subtitles(video['url'], team_dir)

            if not audio_path:
                continue

            processed_videos.append(video['id'])

            # 字幕から選手セグメントを抽出
            if sub_path:
                print(f"   📝 字幕解析中...")
                player_segments = parse_vtt_for_players(sub_path)

                if player_segments:
                    print(f"   検出された選手: {', '.join(player_segments.keys())}")

                    for player, segments in player_segments.items():
                        # 対象選手のフィルタリング
                        if target_player and player != target_player.lower():
                            continue

                        if player not in collected:
                            collected[player] = []

                        # 各セグメントからエンベディング抽出
                        for seg in segments[:15]:  # 動画あたり最大15セグメント
                            if seg['end'] - seg['start'] < 1.5:  # 1.5秒以上
                                continue

                            emb = extract_embedding(
                                audio_path, seg['start'], seg['end'], encoder
                            )
                            if emb is not None:
                                collected[player].append({
                                    'embedding': emb,
                                    'video_id': video['id'],
                                    'start': seg['start'],
                                    'end': seg['end'],
                                })

                        print(f"      {player}: {len(collected.get(player, []))}セグメント")
                else:
                    print("   ⚠️ 字幕から選手名が検出できませんでした")
                    # 字幕なしの場合はWhisperでフォールバック
                    print("   🎙️ Whisperで発話検出...")
                    segments = detect_speech_segments(audio_path)
                    print(f"   ⚠️ {len(segments)}セグメント検出（選手不明）")
            else:
                print("   ⚠️ 字幕が見つかりませんでした")

    # 結果サマリー
    print(f"\n{'='*60}")
    print(f"📊 収集結果サマリー")
    print(f"{'='*60}")

    results = {}
    for player, segments in collected.items():
        count = len(segments)
        results[player] = count
        print(f"   {player}: {count}セグメント")

        # エンベディング更新
        if update_embedding and count >= 3:  # 3セグメント以上で更新
            print(f"   🔄 {player}のエンベディング更新中...")
            embeddings = [seg['embedding'] for seg in segments]
            success = update_player_embedding(player.capitalize(), embeddings)

            if success:
                print(f"   ✅ {player}のエンベディングを更新しました")

                # データベース更新
                db = load_database()
                player_cap = player.capitalize()
                if player_cap in db.get('players', {}):
                    db['players'][player_cap]['accuracy']['source'] = 'team_voice'
                    db['players'][player_cap]['accuracy']['collected_segments'] = count
                    save_database(db)

    if not results:
        print("   ⚠️ 選手音声を収集できませんでした")
        print("   💡 字幕付きのチームボイス動画を探してください")

    return results


def search_youtube(query: str, max_results: int = 5) -> list:
    """YouTubeで動画を検索"""
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'default_search': 'ytsearch',
    }

    search_query = f"ytsearch{max_results}:{query}"

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            result = ydl.extract_info(search_query, download=False)
            if 'entries' in result:
                videos = []
                for entry in result['entries']:
                    if entry:
                        videos.append({
                            'id': entry.get('id'),
                            'title': entry.get('title'),
                            'url': f"https://www.youtube.com/watch?v={entry.get('id')}",
                            'duration': entry.get('duration', 0),
                        })
                return videos
    except Exception as e:
        print(f"   検索エラー: {e}")

    return []


def download_audio(url: str, output_dir: str, max_duration: int = 1800) -> str:
    """YouTube動画から音声をダウンロード"""
    os.makedirs(output_dir, exist_ok=True)

    # 共通オプション（403エラー回避）
    common_opts = {
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {'youtube': {'player_client': ['android', 'web']}},
        'http_headers': {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
    }

    try:
        # 動画情報を取得
        with yt_dlp.YoutubeDL(common_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration = info.get('duration', 0)
            video_id = info.get('id')
            title = info.get('title', 'unknown')

            # 長すぎる動画はスキップ
            if duration > max_duration:
                print(f"   ⚠️ 動画が長すぎます ({duration}秒 > {max_duration}秒)")
                return None

        # 音声ダウンロード
        audio_path = os.path.join(output_dir, f"{video_id}.wav")

        if os.path.exists(audio_path):
            print(f"   ♻️ キャッシュ使用: {video_id}")
            return audio_path

        ydl_opts = {
            **common_opts,
            'format': 'bestaudio[ext=m4a]/bestaudio/best',
            'outtmpl': os.path.join(output_dir, f"{video_id}.%(ext)s"),
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'wav',
            }],
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        return audio_path

    except Exception as e:
        print(f"   ダウンロードエラー: {e}")
        return None


def detect_speech_segments(audio_path: str, min_speech_duration: float = 2.0) -> list:
    """音声から発話区間を検出（Whisperベース）"""
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language="ko")

        segments = []
        for seg in result['segments']:
            duration = seg['end'] - seg['start']
            if duration >= min_speech_duration:
                segments.append({
                    'start': seg['start'],
                    'end': seg['end'],
                    'text': seg['text'].strip(),
                    'duration': duration,
                })

        return segments

    except Exception as e:
        print(f"   発話検出エラー: {e}")
        return []


def extract_embedding(audio_path: str, start: float, end: float, encoder) -> np.ndarray:
    """音声セグメントからエンベディングを抽出"""
    try:
        waveform, sr = torchaudio.load(audio_path)

        # モノラルに変換
        if waveform.shape[0] > 1:
            waveform = waveform.mean(dim=0, keepdim=True)

        # リサンプリング（16kHz）
        if sr != 16000:
            resampler = torchaudio.transforms.Resample(sr, 16000)
            waveform = resampler(waveform)
            sr = 16000

        start_sample = int(start * sr)
        end_sample = int(end * sr)

        # セグメント抽出
        segment = waveform[:, start_sample:end_sample]

        if segment.shape[1] < sr:  # 1秒未満はスキップ
            return None

        # エンベディング計算
        emb = encoder.encode_batch(segment).squeeze().numpy()

        # 形状確認（192,）であるべき
        if len(emb.shape) != 1 or emb.shape[0] != 192:
            print(f"   ⚠️ エンベディング形状異常: {emb.shape}")
            return None

        return emb

    except Exception as e:
        print(f"   エンベディング抽出エラー: {e}")
        return None


# セッションバックアップフラグ（同一セッションで複数回バックアップを避ける）
_session_backup_created = False


def update_player_embedding(player_name: str, new_embeddings: list, weight_new: float = 0.2,
                            auto_backup: bool = True):
    """選手のエンベディングを更新（自動バックアップ付き）"""
    global _session_backup_created

    if not new_embeddings:
        return False

    emb_path = os.path.join(EMBEDDINGS_DIR, f'{player_name.lower()}.npy')

    # 既存ファイルがある場合、セッション最初の更新前にバックアップ
    if auto_backup and os.path.exists(emb_path) and not _session_backup_created:
        print("   💾 更新前バックアップ作成中...")
        create_backup(reason="auto_before_update")
        _session_backup_created = True

    # 新しいエンベディングの平均
    new_emb = np.mean(new_embeddings, axis=0)

    if os.path.exists(emb_path):
        existing = np.load(emb_path)
        # 重み付け結合
        combined = (1 - weight_new) * existing + weight_new * new_emb
        combined = combined / np.linalg.norm(combined) * np.linalg.norm(existing)
    else:
        combined = new_emb

    np.save(emb_path, combined)
    return True


def reset_session_backup_flag():
    """セッションバックアップフラグをリセット"""
    global _session_backup_created
    _session_backup_created = False


def collect_player_voice(player_name: str, max_videos: int = 3,
                         update_embedding: bool = True) -> dict:
    """選手の音声を収集してエンベディングを更新"""
    player_lower = player_name.lower()
    player_dir = os.path.join(COLLECT_DIR, player_lower)
    os.makedirs(player_dir, exist_ok=True)

    print(f"\n{'='*50}")
    print(f"🎤 {player_name} の音声収集")
    print(f"{'='*50}")

    # 検索キーワード取得
    keywords = PLAYER_SEARCH_KEYWORDS.get(player_lower, [f"{player_name} interview"])

    collected_segments = []
    processed_videos = []

    # エンコーダー初期化
    encoder = EncoderClassifier.from_hparams(
        source='speechbrain/spkrec-ecapa-voxceleb',
        savedir=CACHE_DIR
    )

    for keyword in keywords:
        print(f"\n🔍 検索: {keyword}")
        videos = search_youtube(keyword, max_results=max_videos)

        for video in videos:
            if video['id'] in processed_videos:
                continue

            print(f"\n📹 {video['title'][:50]}...")
            print(f"   URL: {video['url']}")

            # 音声ダウンロード
            audio_path = download_audio(video['url'], player_dir)
            if not audio_path:
                continue

            # 発話区間検出
            print("   🎙️ 発話区間検出中...")
            segments = detect_speech_segments(audio_path)
            print(f"   検出: {len(segments)}セグメント")

            # エンベディング抽出
            for seg in segments[:10]:  # 最大10セグメント
                emb = extract_embedding(audio_path, seg['start'], seg['end'], encoder)
                if emb is not None:
                    collected_segments.append({
                        'embedding': emb,
                        'text': seg['text'],
                        'video_id': video['id'],
                        'start': seg['start'],
                        'end': seg['end'],
                    })

            processed_videos.append(video['id'])

            if len(collected_segments) >= 20:  # 十分なセグメントが集まったら終了
                break

        if len(collected_segments) >= 20:
            break

    print(f"\n📊 収集結果: {len(collected_segments)}セグメント")

    # エンベディング更新
    if update_embedding and collected_segments:
        print("\n🔄 エンベディング更新中...")
        embeddings = [seg['embedding'] for seg in collected_segments]
        success = update_player_embedding(player_name, embeddings)

        if success:
            print(f"✅ {player_name}のエンベディングを更新しました")

            # データベース更新
            db = load_database()
            if player_name in db.get('players', {}):
                db['players'][player_name]['accuracy']['source'] = 'auto_collected'
                db['players'][player_name]['accuracy']['collected_segments'] = len(collected_segments)
                save_database(db)

    return {
        'player': player_name,
        'segments_collected': len(collected_segments),
        'videos_processed': len(processed_videos),
        'segments': collected_segments,
    }


def collect_team_voices(team_name: str, **kwargs):
    """チーム全員の音声を収集"""
    db = load_database()

    if team_name not in db.get('teams', {}):
        print(f"❌ チーム {team_name} が見つかりません")
        return

    players = db['teams'][team_name]['players']

    print(f"\n{'='*50}")
    print(f"🏆 {team_name} 全選手の音声収集")
    print(f"{'='*50}")
    print(f"選手: {', '.join(players)}")

    results = []
    for player in players:
        result = collect_player_voice(player, **kwargs)
        results.append(result)

    # サマリー
    print(f"\n{'='*50}")
    print(f"📊 {team_name} 収集サマリー")
    print(f"{'='*50}")
    for r in results:
        status = "✅" if r['segments_collected'] > 0 else "❌"
        print(f"  {status} {r['player']}: {r['segments_collected']}セグメント")


def collect_team_voice_videos(team_name: str, max_videos: int = 3):
    """チームボイス動画から音声を収集"""
    print(f"\n{'='*50}")
    print(f"🎮 {team_name} チームボイス動画収集")
    print(f"{'='*50}")

    keywords = TEAM_VOICE_KEYWORDS.get(team_name, [f"{team_name} team voice"])
    team_dir = os.path.join(COLLECT_DIR, f"team_voice_{team_name.lower()}")
    os.makedirs(team_dir, exist_ok=True)

    for keyword in keywords:
        print(f"\n🔍 検索: {keyword}")
        videos = search_youtube(keyword, max_results=max_videos)

        for video in videos:
            print(f"\n📹 {video['title'][:50]}...")
            print(f"   URL: {video['url']}")
            print(f"   ⚠️ チームボイス動画は手動でラベリングが必要です")
            print(f"   コマンド例: python clip_with_speaker.py '{video['url']}' 0:00 1:00 --learn")


def main():
    parser = argparse.ArgumentParser(description='選手の音声を自動収集')
    parser.add_argument('player', nargs='?', help='選手名')
    parser.add_argument('--team', '-t', help='チーム全員を収集（インタビュー動画）')
    parser.add_argument('--team-voice-auto', '-tva', help='チームボイス動画から自動収集（字幕ベース）')
    parser.add_argument('--diarize', '-d', help='話者照合で収集（推奨・最も精度が高い）')
    parser.add_argument('--player', '-p', dest='target_player', help='対象選手（--team-voice-autoと併用）')
    parser.add_argument('--all', '-a', action='store_true', help='全選手を収集')
    parser.add_argument('--team-voice', '-tv', help='チームボイス動画を検索（手動用）')
    parser.add_argument('--max-videos', '-m', type=int, default=5, help='検索する動画数')
    parser.add_argument('--collect-only', action='store_true', help='収集のみ（更新なし）')
    parser.add_argument('--list', '-l', action='store_true', help='登録選手一覧')

    # バックアップ/復元オプション
    parser.add_argument('--backup', '-b', action='store_true', help='エンベディングをバックアップ')
    parser.add_argument('--restore', '-r', nargs='?', const='latest', help='バックアップから復元（名前指定可）')
    parser.add_argument('--restore-player', help='特定選手のエンベディングを復元')
    parser.add_argument('--list-backups', action='store_true', help='バックアップ一覧を表示')

    args = parser.parse_args()

    if args.list:
        db = load_database()
        print("\n登録選手一覧:")
        for team, info in db.get('teams', {}).items():
            print(f"\n【{team}】")
            for player in info['players']:
                player_info = db.get('players', {}).get(player, {})
                acc = player_info.get('accuracy', {})
                level = acc.get('level', 'unknown')
                print(f"  - {player} ({level})")
        return

    if args.list_backups:
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
        return

    if args.backup:
        print("\n💾 手動バックアップ作成中...")
        create_backup(reason="manual")
        print("✅ バックアップ完了")
        return

    if args.restore:
        backup_name = None if args.restore == 'latest' else args.restore
        print(f"\n🔄 バックアップから復元中...")
        if backup_name:
            print(f"   対象: {backup_name}")
        else:
            print("   対象: 最新のバックアップ")
        restore_backup(backup_name)
        return

    if args.restore_player:
        print(f"\n🔄 {args.restore_player} のエンベディングを復元中...")
        restore_player_embedding(args.restore_player)
        return

    if args.diarize:
        collect_with_diarization(
            args.diarize,
            target_player=args.target_player,
            max_videos=args.max_videos,
            update_embedding=not args.collect_only
        )
        return

    if args.team_voice_auto:
        collect_from_team_voice(
            args.team_voice_auto,
            target_player=args.target_player,
            max_videos=args.max_videos,
            update_embedding=not args.collect_only
        )
        return

    if args.team_voice:
        collect_team_voice_videos(args.team_voice, max_videos=args.max_videos)
        return

    if args.team:
        collect_team_voices(
            args.team,
            max_videos=args.max_videos,
            update_embedding=not args.collect_only
        )
        return

    if args.all:
        db = load_database()
        for team in db.get('teams', {}).keys():
            collect_team_voices(
                team,
                max_videos=args.max_videos,
                update_embedding=not args.collect_only
            )
        return

    if args.player:
        collect_player_voice(
            args.player,
            max_videos=args.max_videos,
            update_embedding=not args.collect_only
        )
        return

    parser.print_help()
    print("\n使用例:")
    print("  # 【最推奨】話者照合で収集（既存エンベディングと照合）")
    print("  python auto_collect_voice.py --diarize T1")
    print()
    print("  # 特定選手のみ収集")
    print("  python auto_collect_voice.py --diarize T1 --player Faker")
    print()
    print("  # 収集のみ（エンベディング更新なし）")
    print("  python auto_collect_voice.py --diarize T1 --collect-only")
    print()
    print("  # 登録選手一覧")
    print("  python auto_collect_voice.py --list")
    print()
    print("  # バックアップ/復元")
    print("  python auto_collect_voice.py --backup              # 手動バックアップ")
    print("  python auto_collect_voice.py --list-backups        # バックアップ一覧")
    print("  python auto_collect_voice.py --restore             # 最新から復元")
    print("  python auto_collect_voice.py --restore backup_xxx  # 指定から復元")
    print("  python auto_collect_voice.py --restore-player Faker # 特定選手のみ復元")


if __name__ == "__main__":
    main()
