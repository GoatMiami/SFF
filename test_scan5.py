import sys
sys.path.insert(0, r'c:\Users\test\OneDrive\Documents\PROJECTS\SFF')
from pathlib import Path
from sff.gui.bridges.misc_bridge import _bridge__scan_installed_games
import json
class B:
    _steam_path=Path('d:/steam')
games = json.loads(_bridge__scan_installed_games(B()))
for g in games:
    if str(g['app_id']) == '4080220':
        print(repr(g))
