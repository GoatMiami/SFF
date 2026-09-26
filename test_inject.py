import requests, json
from websocket import create_connection

tabs = requests.get('http://localhost:8080/json').json()
store_tab = next((t for t in tabs if 'store.steampowered.com' in t.get('url','')), None)
if not store_tab:
    print('NO STORE TAB FOUND')
    for t in tabs:
        print(' -', t.get('title'), '|', t.get('url','')[:80])
else:
    print('Found tab:', store_tab['title'], '|', store_tab['url'])
    ws = create_connection(store_tab['webSocketDebuggerUrl'], timeout=5)
    js = """
var d = document.createElement('div');
d.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;background:red;z-index:2147483647;color:white;font-size:50px;display:flex;align-items:center;justify-content:center';
d.innerText = 'STEAMIDRA WORKS';
document.body.appendChild(d);
"""
    ws.send(json.dumps({'id':1,'method':'Runtime.evaluate','params':{'expression': js, 'returnByValue':True}}))
    resp = ws.recv()
    print('Response:', resp)
    ws.close()
