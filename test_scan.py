import sys
sys.path.insert(0, r'c:\Users\test\OneDrive\Documents\PROJECTS\SFF')
import json
from pathlib import Path
from sff.gui.bridges.misc_bridge import _bridge__scan_installed_games

class MockBridge:
    _steam_path = Path('d:/steam')
    _steamidra_managed_sources = {}
    
    def _run_async(self, f, on_done=None):
        games = f()
        print("Total games:", len(games))
        for g in games:
            if "ea sports" in g["name"].lower() or "4739660" in str(g["app_id"]):
                print("EA FC:", g)
            elif g.get("steamidra_source"):
                print("Managed:", g)

    def _emit_task_result(self, task, ok, msg, **kwargs):
        pass

b = MockBridge()
_bridge__scan_installed_games(b)
