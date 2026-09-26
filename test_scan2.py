import sys
sys.path.insert(0, r'c:\Users\test\OneDrive\Documents\PROJECTS\SFF')
from pathlib import Path
from sff.gui.bridges.misc_bridge import _bridge__scan_installed_games

class B:
    _steam_path = Path('d:/steam')
    def _run_async(self, f, on_done=None):
        res = f()
        print("Total returned games:", len(res))
        for g in res:
            if "ea sports" in g["name"].lower() or "4739660" in str(g["app_id"]):
                print("EA FC:", g)
    def _emit_task_result(self, *args, **kwargs):
        pass

b = B()
_bridge__scan_installed_games(b)
