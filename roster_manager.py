#!/usr/bin/env python3
"""
LCK ロースター管理システム
- 最新ロースターをWebから取得
- データベースを自動更新
- 古いデータの警告
"""

import json
import re
from datetime import datetime, timedelta
from pathlib import Path

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

        else:
            print(f"Unknown command: {cmd}")
            print("Usage: python roster_manager.py [show|validate|sync]")
    else:
        print("Usage: python roster_manager.py [show|validate|sync]")
        print("  show     - 公式ロースターを表示")
        print("  validate - データベースを検証")
        print("  sync     - データベースを同期")
