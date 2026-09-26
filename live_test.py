import requests
import json
import time
from websocket import create_connection

JS_POPUP = """
(function() {
    var appId = window.location.pathname.match(/\\/app\\/(\\d+)/);
    if (!appId) return;
    appId = appId[1];
    if (document.getElementById('steamidra-popup')) return;
    var overlay = document.createElement('div');
    overlay.id = 'steamidra-popup';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:rgba(0,0,0,0.85);z-index:2147483647;display:flex;align-items:center;justify-content:center;flex-direction:column;font-family:Arial,sans-serif';
    var box = document.createElement('div');
    box.style.cssText = 'background:#1a9fff;color:white;padding:40px 60px;border-radius:12px;text-align:center;box-shadow:0 8px 40px rgba(0,0,0,0.6)';
    box.innerHTML = '<h1 style="margin:0 0 10px 0;font-size:28px">Add to SteaMidra Library</h1><p style="margin:0 0 20px 0;font-size:16px">App ID: ' + appId + '</p><button onclick="this.parentNode.parentNode.remove()" style="background:white;color:#1a9fff;border:none;padding:10px 30px;border-radius:6px;font-size:16px;font-weight:bold;cursor:pointer">Dismiss</button>';
    overlay.appendChild(box);
    document.body.appendChild(overlay);
})();
"""

def inject(tab_id):
    ws = create_connection(f"ws://localhost:8080/devtools/page/{tab_id}", timeout=10)
    ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": JS_POPUP}}))
    print("  -> inject response:", ws.recv()[:100])
    ws.close()

version = requests.get("http://localhost:8080/json/version").json()
browser_ws_url = version["webSocketDebuggerUrl"]
print("Connected to Steam browser:", browser_ws_url)

ws = create_connection(browser_ws_url)
ws.send(json.dumps({"id": 1, "method": "Target.setDiscoverTargets", "params": {"discover": True}}))

seen = {}  # tab_id -> url

print("Watching for URL changes... Navigate to a game in Steam now.")
while True:
    msg = json.loads(ws.recv())
    method = msg.get("method", "")
    if method in ("Target.targetCreated", "Target.targetInfoChanged"):
        info = msg.get("params", {}).get("targetInfo", {})
        tab_id = info.get("targetId", "")
        url = info.get("url", "")
        if url != seen.get(tab_id):
            seen[tab_id] = url
            print(f"URL change: {url[:80]}")
            if "/app/" in url:
                print("  -> GAME PAGE DETECTED, injecting...")
                time.sleep(1)
                inject(tab_id)
