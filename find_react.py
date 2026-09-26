import urllib.request, json
from websocket import create_connection

try:
    resp = urllib.request.urlopen('http://127.0.0.1:8080/json')
    pages = json.loads(resp.read())
    ws_url = [p['webSocketDebuggerUrl'] for p in pages if 'library/home' in p['url']][0]
    ws = create_connection(ws_url)
    cmd = {
        'id': 1, 
        'method': 'Runtime.evaluate', 
        'params': {
            'expression': """(function(){
                let focusable = null;
                window.webpackChunksteamui.push([[Math.random()], {}, (r) => {
                    for (let m in r.m) {
                        try {
                            let mod = r(m);
                            if (mod && mod.Focusable) focusable = true;
                        } catch(e) {}
                    }
                }]);
                return {focusable: focusable};
            })()""", 
            'returnByValue': True
        }
    }
    ws.send(json.dumps(cmd))
    print(ws.recv())
except Exception as e:
    print(e)
