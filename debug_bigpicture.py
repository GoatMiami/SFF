import requests
import json
from websocket import create_connection

tabs = requests.get('http://localhost:8080/json').json()
store_tab = next((t for t in tabs if 'store.steampowered.com/app/' in t.get('url', '')), None)
if not store_tab:
    print("No game page open.")
    exit()

print(f"Tab: {store_tab['url']}")
ws = create_connection(store_tab['webSocketDebuggerUrl'], timeout=10)

# 1. Dump the actual outerHTML of StoreSalePriceWidgetContainer
ws.send(json.dumps({'id': 1, 'method': 'Runtime.evaluate', 'params': {
    'expression': '''
    var el = document.querySelector(".StoreSalePriceWidgetContainer");
    el ? el.outerHTML.substring(0, 400) : "NOT FOUND";
    ''',
    'returnByValue': True
}}))
resp = json.loads(ws.recv())
print("\n.StoreSalePriceWidgetContainer outerHTML:")
print(resp.get('result',{}).get('result',{}).get('value',''))

# 2. Actually inject a test button into it directly
ws.send(json.dumps({'id': 2, 'method': 'Runtime.evaluate', 'params': {
    'expression': '''
    var el = document.querySelector(".StoreSalePriceWidgetContainer");
    if (el) {
        var b = document.createElement("div");
        b.id = "steamidra-test";
        b.style = "background:red;color:white;padding:10px;font-size:20px;font-weight:bold";
        b.innerText = "STEAMIDRA TEST BUTTON";
        el.appendChild(b);
        "INJECTED";
    } else {
        "NOT FOUND";
    }
    ''',
    'returnByValue': True
}}))
resp = json.loads(ws.recv())
print("\nDirect inject result:", resp.get('result',{}).get('result',{}).get('value',''))

ws.close()
