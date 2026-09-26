import sys
sys.path.insert(0, r'c:\Users\test\OneDrive\Documents\PROJECTS\SFF')
from pathlib import Path
from sff.gui.bridges.misc_bridge import _bridge__scan_installed_games
import json
class B:
    _steam_path=Path('d:/steam')
games = json.loads(_bridge__scan_installed_games(B()))
for g in games:
    if not g['name'].strip() or g['name'].startswith(' (Uninstalled)') or g['name'].startswith('App '):
        print(g['app_id'], repr(g['name']))
