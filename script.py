import requests
from websocket import create_connection
import json
tabs = requests.get('http://localhost:8080/json').json()
for tab in tabs:
    if tab.get('title') == 'Steam':
        ws_url = tab['webSocketDebuggerUrl']
        ws = create_connection(ws_url, timeout=5)
        # Search for iframe, webview, or frame in all shadow roots too
        req = json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {'expression': 'Array.from(document.querySelectorAll("*")).filter(e=>e.tagName=="IFRAME" || e.tagName=="WEBVIEW").map(e=>e.src).join(",");', 'returnByValue': True}})
        ws.send(req)
        print("Frames:", ws.recv())
        ws.close()
