# Steam CDP Injection — Knowledge Base

Learned through trial, error, and live debugging. Read this before touching `steam_injector.py`.

---

## How Steam's Browser Works

Steam's desktop client uses **Chromium Embedded Framework (CEF)**. It exposes a Chrome DevTools Protocol (CDP) debug port when launched with:

```
steam.exe -cef-enable-debugging -cef-port=8080
```

Once running, you can hit `http://localhost:8080/json` to list all active CEF targets (tabs).

---

## Tab Structure — What You'll Find at /json

Steam runs many internal CEF targets simultaneously. The important ones:

| Title | URL | Purpose |
|---|---|---|
| `Welcome to Steam` / game title | `https://store.steampowered.com/...` | The **actual store page** — inject here |
| `SharedJSContext` | `https://steamloopback.host/index.html?...` | Steam's global React context — do NOT inject UI here |
| `Steam` | `about:blank?createflags=274...` | Steam's shell window — not useful for store injection |
| `Store Supernav`, `Library Supernav`, etc. | `about:blank?createflags=4538634...` | Navigation bars — ignore |

**The store tab is the only one with `store.steampowered.com` in its URL.**

---

## Critical Lesson: Steam Store is NOT a Traditional SPA

### What I assumed (wrong):
Steam uses `history.pushState` for navigation, so patching `pushState` inside the page would catch all navigations.

### What actually happens:
When navigating from the store homepage to a game page, Steam does a **full page load**, not a pushState navigation. This wipes out any JS you injected into the previous page.

### The correct approach:
Use **`Target.targetInfoChanged`** via the browser-level CDP WebSocket (`/json/version` → `webSocketDebuggerUrl`). This event fires every time a tab's URL changes, including full page navigations. Python-side listener is the right approach, not JS-side `pushState` patching.

---

## Browser-Level vs Tab-Level CDP

### Tab-level (inject JS):
```python
ws = create_connection("ws://localhost:8080/devtools/page/{TAB_ID}")
ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": JS_CODE}}))
resp = ws.recv()  # Always wait for recv() or it causes "timed out" next call
ws.close()
```

### Browser-level (listen for events):
```python
version = requests.get("http://localhost:8080/json/version").json()
browser_ws_url = version["webSocketDebuggerUrl"]
ws = create_connection(browser_ws_url)
ws.send(json.dumps({"id": 1, "method": "Target.setDiscoverTargets", "params": {"discover": True}}))
# Now listen — fires for ALL tabs including existing ones
while True:
    msg = json.loads(ws.recv())
    if msg.get("method") in ("Target.targetCreated", "Target.targetInfoChanged"):
        info = msg["params"]["targetInfo"]
        tab_id = info["targetId"]
        url = info["url"]
```

---

## The Duplicate Injection Problem

`Target.targetInfoChanged` fires **multiple times for a single navigation**:

```
https://store.steampowered.com/app/1174180/Red_Dead_Redemption_2?snr=1_5_9__300   ← tracking param
https://store.steampowered.com/app/1174180/Red_Dead_Redemption_2                   ← param stripped
https://store.steampowered.com/app/1174180/Red_Dead_Redemption_2/                  ← trailing slash added
```

### Wrong fix: track by full URL
The URL changes slightly each time, so you'd inject 3 times.

### Correct fix: track by app ID per tab
```python
import re

def get_app_id(url):
    m = re.search(r'store\.steampowered\.com/app/(\d+)', url)
    return m.group(1) if m else None

last_injected = {}  # tab_id -> app_id

def check_and_inject(tab_id, url):
    app_id = get_app_id(url)
    if app_id and last_injected.get(tab_id) != app_id:
        last_injected[tab_id] = app_id
        time.sleep(0.8)  # let DOM settle
        inject_popup(tab_id)
```

---

## Timeout Issue

Early code used `timeout=2` for WebSocket connections. Steam's CEF sometimes takes longer to respond.

**Always use `timeout=10` minimum** for `create_connection`.

Also: **always call `ws.recv()` after `ws.send()`**, even for fire-and-forget. Skipping `recv()` leaves the response in the buffer and causes the next connection attempt to time out.

---

## DOM Injection — Store Page Classes

### Normal Steam Store mode:
```js
document.querySelector('.apphub_HeaderStandardTop')
```
Append button here. It sits at the top-right of the game page header.

### Big Picture / Steam Deck mode:
```js
document.querySelector('.StoreSalePriceWidgetContainer')
```
Append button here. It sits next to the price widget.

### Key insight: both classes exist on the same page
Use two separate injections with separate IDs — do NOT use `||` (it will always pick the first one):

```js
var normalContainer = document.querySelector('.apphub_HeaderStandardTop');
if (normalContainer && !document.getElementById('steamidra-btn-normal')) {
    normalContainer.appendChild(makeBtn('steamidra-btn-normal'));
}

var bpContainer = document.querySelector('.StoreSalePriceWidgetContainer');
if (bpContainer && !document.getElementById('steamidra-btn-bp')) {
    bpContainer.appendChild(makeBtn('steamidra-btn-bp'));
}
```

### DOM settle time
After a URL change event, the page DOM may not be fully loaded. **Add a 0.8–1s delay** before injecting.

---

## steam.cfg — Millennium Leftover

Millennium (Steam skin injector) writes a `steam.cfg` file to the Steam root directory containing:

```
BootStrapperInhibitAll=Enable
```

This blocks Steam from self-updating/repairing. If present after Millennium removal, Steam will fail to launch properly. **Delete or rename `steam.cfg`** if Steam stops opening after Millennium is uninstalled.

---

## wsock32.dll — Millennium DLL Hook

Millennium also drops a patched `wsock32.dll` into the Steam root (`D:\Steam\wsock32.dll`). This DLL intercepts Steam's networking to load Millennium plugins. It must be deleted **while Steam is not running** otherwise it throws a Millennium error on next launch even if Millennium itself was uninstalled.

---

## Working Test Script (Standalone)

Use this to validate injection is working independently of SteaMidra:

```python
import requests, json, time
from websocket import create_connection
import re

def get_app_id(url):
    m = re.search(r'store\.steampowered\.com/app/(\d+)', url)
    return m.group(1) if m else None

version = requests.get("http://localhost:8080/json/version").json()
ws = create_connection(version["webSocketDebuggerUrl"])
ws.send(json.dumps({"id": 1, "method": "Target.setDiscoverTargets", "params": {"discover": True}}))

seen = {}
while True:
    msg = json.loads(ws.recv())
    if msg.get("method") in ("Target.targetCreated", "Target.targetInfoChanged"):
        info = msg["params"]["targetInfo"]
        tab_id, url = info["targetId"], info["url"]
        app_id = get_app_id(url)
        if app_id and seen.get(tab_id) != app_id:
            seen[tab_id] = app_id
            print(f"Game page: {url}")
            time.sleep(0.8)
            tab_ws = create_connection(f"ws://localhost:8080/devtools/page/{tab_id}", timeout=10)
            tab_ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": "document.title"}}))
            print("Inject result:", tab_ws.recv())
            tab_ws.close()
```

---

## Final Architecture in SteaMidra

- `sff/steam_injector.py` — the injector module
- Called once on app start via `start_injector()` which spins a daemon thread
- Thread runs `injection_loop()` which:
  1. Ensures Steam is running with debug port open (restarts if needed)
  2. Scans existing tabs immediately
  3. Opens browser-level CDP WebSocket and listens for `targetInfoChanged`
  4. Injects JS into any tab whose URL matches `/app/{id}/`
  5. Auto-reconnects if Steam restarts (outer `while True` loop)
