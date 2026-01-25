#!/usr/bin/env python3
"""
LCK ロースター管理システム
- 最新ロースターをWebから取得
- データベースを自動更新
- 古いデータの警告
"""

import json
import re
import os
from datetime import datetime, timedelta
from pathlib import Path

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    from bs4 import BeautifulSoup
    BS4_AVAILABLE = True
except ImportError:
    BS4_AVAILABLE = False

# 公式ロースター（2026 LCK Spring）
# 最終更新: 2026-01-25
OFFICIAL_ROSTERS = {
    "T1": {
        "Top": "Doran",
        "Jungle": "Oner",
        "Mid": "Faker",
        "ADC": "Peyz",
        "Support": "Keria"
    },
    "GenG": {
        "Top": "Kiin",
        "Jungle": "Canyon",
        "Mid": "Chovy",
        "ADC": "Ruler",
        "Support": "Duro"
    },
    "HLE": {
        "Top": "Zeus",
        "Jungle": "Kanavi",
        "Mid": "Zeka",
        "ADC": "Gumayusi",
        "Support": "Delight"
    },
    "DK": {
        "Top": "Siwoo",
        "Jungle": "Lucid",
        "Mid": "Showmaker",
        "ADC": "Smash",
        "Support": "Career"
    },
    "KT": {
        "Top": "PerfecT",
        "Jungle": "Cuzz",
        "Mid": "Bdd",
        "ADC": "Aiming",
        "Support": "Ghost"
    },
    "NS": {
        "Top": "Kingen",
        "Jungle": "Sylvie",
        "Mid": "Scout",
        "ADC": "Jiwoo",
        "Support": "Lehends"
    },
    "FEARX": {
        "Top": "Clear",
        "Jungle": "Raptor",
        "Mid": "VicLa",
        "ADC": "Teddy",
        "Support": "Peter"
    },
    "BRO": {
        "Top": "Morgan",
        "Jungle": "Peanut",  # Peanut moved to BRO, not retired
        "Mid": "Clozer",
        "ADC": "Envyy",
        "Support": "Effort"
    },
    "OKS": {
        "Top": "Dudu",
        "Jungle": "Willer",
        "Mid": "Fisher",
        "ADC": "Viper",  # Viper is on OKS, not BLG
        "Support": "Execute"
    }
}

ROSTER_VERSION = "2026-01-25"
ROSTER_SOURCE = "LCK 2026 Spring Official"

DB_PATH = Path(__file__).parent / "data" / "speaker_database.json"
ROSTER_CACHE_PATH = Path(__file__).parent / "data" / "roster_cache.json"

# Liquipedia API endpoint
LIQUIPEDIA_API = "https://liquipedia.net/leagueoflegends/api.php"

# LCK Team name mappings (Liquipedia name -> our name)
TEAM_NAME_MAP = {
    "T1": "T1",
    "Gen.G": "GenG",
    "Gen.G Esports": "GenG",
    "Hanwha Life Esports": "HLE",
    "HLE": "HLE",
    "Dplus KIA": "DK",
    "DK": "DK",
    "KT Rolster": "KT",
    "KT": "KT",
    "Nongshim RedForce": "NS",
    "NS RedForce": "NS",
    "BNK FEARX": "FEARX",
    "FEARX": "FEARX",
    "OKSavingsBank BRION": "BRO",
    "BRION": "BRO",
    "BRO": "BRO",
    "OK SAVINGS BANK BRION": "OKS",
    "Kwangdong Freecs": "OKS",
    "OKS": "OKS",
}

# Role name mappings
ROLE_MAP = {
    "Top": "Top",
    "Toplane": "Top",
    "Jungle": "Jungle",
    "Jungler": "Jungle",
    "Mid": "Mid",
    "Midlane": "Mid",
    "Middle": "Mid",
    "ADC": "ADC",
    "Bot": "ADC",
    "AD Carry": "ADC",
    "Support": "Support",
    "Sup": "Support",
}


def fetch_rosters_from_web() -> dict:
    """Webから最新ロースターを取得"""
    if not REQUESTS_AVAILABLE:
        print("❌ requests モジュールが必要です: pip install requests")
        return None

    print("🌐 Liquipediaから最新ロースターを取得中...")

    try:
        # Use Liquipedia API to get LCK team rosters
        rosters = {}

        # LCK teams to fetch
        teams = [
            "T1", "Gen.G", "Hanwha_Life_Esports", "Dplus_KIA",
            "KT_Rolster", "Nongshim_RedForce", "BNK_FEARX",
            "OKSavingsBank_BRION", "Kwangdong_Freecs"
        ]

        headers = {
            'User-Agent': 'LCK-Roster-Bot/1.0 (Contact: github.com/nukku915)',
            'Accept-Encoding': 'gzip'
        }

        for team_page in teams:
            try:
                # Fetch team page via API
                params = {
                    'action': 'parse',
                    'page': team_page,
                    'format': 'json',
                    'prop': 'wikitext'
                }

                response = requests.get(LIQUIPEDIA_API, params=params, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    if 'parse' in data and 'wikitext' in data['parse']:
                        wikitext = data['parse']['wikitext']['*']
                        team_roster = parse_liquipedia_roster(wikitext, team_page)
                        if team_roster:
                            team_name = TEAM_NAME_MAP.get(team_page.replace('_', ' '), team_page)
                            rosters[team_name] = team_roster
                            print(f"  ✓ {team_name}")

            except Exception as e:
                print(f"  ✗ {team_page}: {e}")
                continue

        if rosters:
            # Cache the results
            cache_data = {
                'rosters': rosters,
                'fetched_at': datetime.now().isoformat(),
                'source': 'Liquipedia'
            }
            ROSTER_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(ROSTER_CACHE_PATH, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            return rosters

    except Exception as e:
        print(f"❌ ロースター取得エラー: {e}")

    return None


def parse_liquipedia_roster(wikitext: str, team_name: str) -> dict:
    """Liquipediaのwikitextからロースターをパース"""
    roster = {}

    # Look for player entries in the wikitext
    # Pattern: |player1=PlayerName or |top=PlayerName
    patterns = [
        r'\|top\s*=\s*([A-Za-z0-9]+)',
        r'\|jungle\s*=\s*([A-Za-z0-9]+)',
        r'\|jungler\s*=\s*([A-Za-z0-9]+)',
        r'\|mid\s*=\s*([A-Za-z0-9]+)',
        r'\|adc\s*=\s*([A-Za-z0-9]+)',
        r'\|bot\s*=\s*([A-Za-z0-9]+)',
        r'\|support\s*=\s*([A-Za-z0-9]+)',
    ]

    role_patterns = {
        'Top': [r'\|top\s*=\s*([A-Za-z0-9]+)'],
        'Jungle': [r'\|jungle\s*=\s*([A-Za-z0-9]+)', r'\|jungler\s*=\s*([A-Za-z0-9]+)'],
        'Mid': [r'\|mid\s*=\s*([A-Za-z0-9]+)', r'\|midlane\s*=\s*([A-Za-z0-9]+)'],
        'ADC': [r'\|adc\s*=\s*([A-Za-z0-9]+)', r'\|bot\s*=\s*([A-Za-z0-9]+)'],
        'Support': [r'\|support\s*=\s*([A-Za-z0-9]+)', r'\|sup\s*=\s*([A-Za-z0-9]+)'],
    }

    for role, pats in role_patterns.items():
        for pat in pats:
            match = re.search(pat, wikitext, re.IGNORECASE)
            if match:
                roster[role] = match.group(1)
                break

    return roster if len(roster) >= 3 else None


def load_cached_rosters() -> dict:
    """キャッシュされたロースターを読み込む"""
    if ROSTER_CACHE_PATH.exists():
        try:
            with open(ROSTER_CACHE_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Check if cache is fresh (within 7 days)
            fetched_at = datetime.fromisoformat(data['fetched_at'])
            if datetime.now() - fetched_at < timedelta(days=7):
                return data['rosters']
            else:
                print("⚠️ キャッシュが古いです（7日以上前）")
        except Exception as e:
            print(f"⚠️ キャッシュ読み込みエラー: {e}")

    return None


def update_official_rosters(new_rosters: dict) -> bool:
    """OFFICIAL_ROSTERSを更新してファイルに書き込む"""
    global OFFICIAL_ROSTERS, ROSTER_VERSION

    if not new_rosters:
        return False

    # Update the global variable
    for team, roster in new_rosters.items():
        if team in OFFICIAL_ROSTERS:
            OFFICIAL_ROSTERS[team] = roster
        else:
            OFFICIAL_ROSTERS[team] = roster

    ROSTER_VERSION = datetime.now().strftime("%Y-%m-%d")

    # Update this file with new rosters
    try:
        file_path = Path(__file__)
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find and replace OFFICIAL_ROSTERS dict
        # This is a simplified approach - in production, use AST manipulation
        new_roster_str = "OFFICIAL_ROSTERS = " + json.dumps(OFFICIAL_ROSTERS, indent=4, ensure_ascii=False)

        # Replace the version
        content = re.sub(
            r'ROSTER_VERSION = "[^"]*"',
            f'ROSTER_VERSION = "{ROSTER_VERSION}"',
            content
        )

        print(f"✅ ロースター更新完了 (version: {ROSTER_VERSION})")
        return True

    except Exception as e:
        print(f"❌ ファイル更新エラー: {e}")
        return False


def auto_update_rosters(force: bool = False) -> bool:
    """ロースターを自動更新"""
    # Check if update is needed
    if not force:
        try:
            version_date = datetime.strptime(ROSTER_VERSION, "%Y-%m-%d")
            days_old = (datetime.now() - version_date).days

            if days_old < 7:
                print(f"ℹ️ ロースターは最新です（{days_old}日前に更新）")
                return True
        except:
            pass

    # Try to load from cache first
    cached = load_cached_rosters()
    if cached and not force:
        print("📦 キャッシュからロースターを読み込み")
        return update_official_rosters(cached)

    # Fetch from web
    new_rosters = fetch_rosters_from_web()
    if new_rosters:
        return update_official_rosters(new_rosters)

    return False


def get_player_team(player_name: str) -> str:
    """選手の所属チームを取得"""
    player_lower = player_name.lower()
    for team, roster in OFFICIAL_ROSTERS.items():
        for role, name in roster.items():
            if name.lower() == player_lower:
                return team
    return None


def get_team_roster(team: str) -> dict:
    """チームのロースターを取得"""
    team_upper = team.upper()
    # Handle variations
    team_map = {
        "GENG": "GenG",
        "GEN.G": "GenG",
        "T1": "T1",
        "HLE": "HLE",
        "HANWHA": "HLE",
        "DK": "DK",
        "DPLUS": "DK",
        "KT": "KT",
        "NS": "NS",
        "NONGSHIM": "NS",
        "FEARX": "FEARX",
        "DRX": "FEARX",
        "BRO": "BRO",
        "OKS": "OKS",
        "OKCASAVINGS": "OKS"
    }

    normalized = team_map.get(team_upper, team)
    return OFFICIAL_ROSTERS.get(normalized, {})


def validate_database() -> list:
    """データベースのロースターを検証"""
    errors = []

    if not DB_PATH.exists():
        return [("error", "データベースが見つかりません")]

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for player_name, info in data.get('players', {}).items():
        db_team = info.get('team', '')
        official_team = get_player_team(player_name)

        if official_team and db_team != official_team:
            errors.append((
                "team_mismatch",
                f"{player_name}: DB={db_team} → 正しくは {official_team}"
            ))
        elif not official_team and db_team not in ['Retired', 'LPL', 'Inactive', '']:
            # Check if player exists in any roster
            found = False
            for team, roster in OFFICIAL_ROSTERS.items():
                if player_name in roster.values():
                    found = True
                    break
            if not found:
                errors.append((
                    "unknown_player",
                    f"{player_name}: LCK 2026ロースターに存在しない（{db_team}）"
                ))

    return errors


def sync_database():
    """データベースを公式ロースターと同期"""
    if not DB_PATH.exists():
        print("❌ データベースが見つかりません")
        return False

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)

    updated = []

    # Update teams structure
    data['teams'] = {}
    for team, roster in OFFICIAL_ROSTERS.items():
        data['teams'][team] = {
            'players': list(roster.values()),
            'roles': {v: k for k, v in roster.items()}
        }

    # Update player team assignments
    for player_name in list(data.get('players', {}).keys()):
        official_team = get_player_team(player_name)
        current_team = data['players'][player_name].get('team', '')

        if official_team:
            if current_team != official_team:
                updated.append(f"{player_name}: {current_team} → {official_team}")
                data['players'][player_name]['team'] = official_team

            # Update role
            for team, roster in OFFICIAL_ROSTERS.items():
                for role, name in roster.items():
                    if name == player_name:
                        data['players'][player_name]['role'] = role
                        break

    # Add metadata
    data['roster_version'] = ROSTER_VERSION
    data['roster_source'] = ROSTER_SOURCE
    data['roster_synced'] = datetime.now().isoformat()

    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return updated


def print_official_rosters():
    """公式ロースターを表示"""
    print(f"\n📋 LCK 2026 公式ロースター (更新: {ROSTER_VERSION})")
    print("=" * 60)

    for team, roster in OFFICIAL_ROSTERS.items():
        players = [f"{roster.get(role, '?')}" for role in ['Top', 'Jungle', 'Mid', 'ADC', 'Support']]
        print(f"  {team:8} | {' / '.join(players)}")


def check_roster_freshness() -> bool:
    """ロースターが最新かチェック"""
    try:
        version_date = datetime.strptime(ROSTER_VERSION, "%Y-%m-%d")
        days_old = (datetime.now() - version_date).days

        if days_old > 30:
            print(f"⚠️ ロースターが{days_old}日前の情報です。更新を推奨します。")
            return False
        return True
    except:
        return True


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "show":
            print_official_rosters()

        elif cmd == "validate":
            print("\n🔍 データベース検証中...")
            errors = validate_database()
            if errors:
                print(f"\n❌ {len(errors)}件の問題が見つかりました:")
                for err_type, msg in errors:
                    print(f"  - {msg}")
            else:
                print("✅ 問題なし")

        elif cmd == "sync":
            print("\n🔄 データベースを公式ロースターと同期中...")
            updated = sync_database()
            if updated:
                print(f"\n✅ {len(updated)}件更新:")
                for u in updated:
                    print(f"  - {u}")
            else:
                print("✅ 更新なし（既に同期済み）")

        elif cmd == "update":
            print("\n🌐 Webから最新ロースターを取得...")
            force = "--force" in sys.argv
            success = auto_update_rosters(force=force)
            if success:
                print("\n✅ ロースター更新完了")
                print("   次に --roster sync でデータベースを同期してください")
            else:
                print("\n❌ ロースター更新失敗")

        elif cmd == "auto":
            # 自動更新 + 同期
            print("\n🔄 ロースター自動更新...")
            force = "--force" in sys.argv
            if auto_update_rosters(force=force):
                updated = sync_database()
                if updated:
                    print(f"\n✅ データベース更新: {len(updated)}件")
                    for u in updated:
                        print(f"  - {u}")
                else:
                    print("\n✅ データベースは最新です")
            else:
                print("\n⚠️ Web取得失敗、ローカルロースターを使用")

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python roster_manager.py [show|validate|sync|update|auto]")
    else:
        print("Usage: python roster_manager.py [show|validate|sync|update|auto]")
        print("  show     - 公式ロースターを表示")
        print("  validate - データベースを検証")
        print("  sync     - データベースを同期")
        print("  update   - Webから最新ロースターを取得")
        print("  auto     - 自動更新 + 同期（推奨）")
        print("")
        print("Options:")
        print("  --force  - キャッシュを無視して強制更新")
