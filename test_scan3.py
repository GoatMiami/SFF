import sys
sys.path.insert(0, r'c:\Users\test\OneDrive\Documents\PROJECTS\SFF')
import json
from pathlib import Path
from sff.gui.bridges.misc_bridge import _bridge__scan_installed_games

class B:
    _steam_path = Path('d:/steam')

b = B()
res = _bridge__scan_installed_games(b)
games = json.loads(res)
print("Total games:", len(games))
for g in games:
    if "ea " in g["name"].lower() or "4739660" in str(g["app_id"]):
        print("EA FC:", g)
