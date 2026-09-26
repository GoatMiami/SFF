import re
import time
import requests
import json
import logging
import threading
import subprocess
import os
from pathlib import Path
from websocket import create_connection
import winreg

logger = logging.getLogger(__name__)


def get_library_app_ids():
    """Return a set of app ID strings that are already present in the SteaMidra
    library.  Scans ALL .lua files from BOTH stplug-in/ and saved_lua/ — not
    just steamidra-managed ones — so the button state is correct for every
    game that SteaMidra has ever written a Lua for.
    """
    app_ids: set = set()
    try:
        from sff.steam_path import init_steam_path
        from sff.core.structs import OSType
        import sys as _sys
        os_type = OSType.WINDOWS if _sys.platform == "win32" else OSType.LINUX
        steam_path = init_steam_path(os_type)
    except Exception:
        steam_path = None

    scan_dirs = []
    try:
        # saved_lua/ lives next to the SteaMidra exe / working dir
        from sff.core.utils import root_folder
        saved_lua = root_folder(outside_internal=True) / "saved_lua"
        if saved_lua.is_dir():
            scan_dirs.append(saved_lua)
    except Exception:
        pass

    if steam_path:
        stplug_in = steam_path / "config" / "stplug-in"
        if stplug_in.is_dir():
            scan_dirs.append(stplug_in)

    for lua_dir in scan_dirs:
        try:
            for lua_file in lua_dir.glob("*.lua"):
                stem = lua_file.stem
                if stem.isdigit():
                    app_ids.add(stem)
        except Exception as e:
            logger.debug("get_library_app_ids: scan of %s failed: %s", lua_dir, e)

    logger.debug("get_library_app_ids: found %d app IDs in library", len(app_ids))
    return app_ids

def _build_js_popup(library_app_ids: set) -> str:
    """Build the JS_POPUP script with the current library state embedded.
    library_app_ids is a set of app ID strings known to be in the library.
    """
    # Serialize as a JS object (hash-set via object keys for O(1) lookup)
    ids_obj = json.dumps({aid: 1 for aid in library_app_ids})

    return f"""
(function() {{
    // Guard: only run on Steam store app pages
    var appIdMatch = window.location.pathname.match(/\\/app\\/(\\d+)/);
    if (!appIdMatch) return;

    // Library state injected from Python at injection time, attached to window
    // so that it can be updated by subsequent update_steam_ui calls.
    window.STEAMIDRA_LIBRARY = {ids_obj};

    // Add spinner + remove-btn CSS once
    if (!document.getElementById('steamidra-styles')) {{
        var style = document.createElement('style');
        style.id = 'steamidra-styles';
        style.innerHTML = [
            '@keyframes steamidra-spin{{0%{{transform:rotate(0deg)}}100%{{transform:rotate(360deg)}}}}',
            '.steamidra-spinner{{display:inline-block;width:14px;height:14px;border:2px solid rgba(255,255,255,0.3);',
            'border-radius:50%;border-top-color:white;animation:steamidra-spin 1s ease-in-out infinite;',
            'vertical-align:middle;margin-right:8px;}}'
        ].join('');
        document.head.appendChild(style);
    }}

    // Determine if the current page app is already in the SteaMidra library
    function isInLibrary(appId) {{
        if (typeof window.STEAMIDRA_LIBRARY === 'undefined') return false;
        return Object.prototype.hasOwnProperty.call(window.STEAMIDRA_LIBRARY, String(appId));
    }}

    // Shared element factory — returns null if the element already exists.
    // For controller (Big Picture) mode we build a single focusable <div>
    // that IS the interactive target (no inner button) matching Valve's own
    // Panel Focusable structure so Steam D-pad navigation picks it up.
    function makeBtn(id, forController) {{
        if (document.getElementById(id)) return null;

        // Read the current page app ID to decide button mode
        var pageMatch = window.location.pathname.match(/\\/app\\/(\\d+)/);
        var pageAppId = pageMatch ? pageMatch[1] : '';
        var isRemove = pageAppId && isInLibrary(pageAppId);

        // Controller mode: single <div role="button"> — no inner button
        // Normal mode:     plain <button>
        var btn = document.createElement(forController ? 'div' : 'button');
        btn.id = forController ? 'steamidra-wrapper-bp' : id;
        if (forController) btn.setAttribute('role', 'button');
        btn.innerText = isRemove ? 'Remove from Library' : 'Add to Library';

        var addGrad  = 'linear-gradient(135deg,#1a9fff,#0074cc)';
        var remGrad  = 'linear-gradient(135deg,#ff4d4d,#cc0000)';
        var baseStyle = [
            'display:block',
            'text-align:center',
            'background:' + (isRemove ? remGrad : addGrad),
            'color:white',
            'font-weight:bold',
            'font-family:Arial,sans-serif',
            'border:none',
            'cursor:pointer',
            'box-shadow:0 2px 8px rgba(0,0,0,0.4)',
            'outline:none'
        ];

        if (forController) {{
            baseStyle.push('margin-top:16px','padding:12px 24px','font-size:16px','border-radius:4px','width:fit-content','margin-left:10px');
        }} else {{
            baseStyle.push('margin-top:10px','padding:10px 20px','font-size:14px','border-radius:3px');
        }}
        btn.style.cssText = baseStyle.join(';');

        function triggerAction() {{
            if (btn.disabled) return;

            // Re-read appId from current URL at click time so navigating
            // between games uses the correct ID.
            var currentMatch = window.location.pathname.match(/\\/app\\/(\\d+)/);
            var currentAppId = currentMatch ? currentMatch[1] : '';
            if (!currentAppId) return;

            var currentIsRemove = isInLibrary(currentAppId);

            btn.disabled = true;
            btn.style.opacity = '0.8';
            btn.style.cursor = 'default';

            if (currentIsRemove) {{
                btn.innerHTML = '<span class="steamidra-spinner"></span>Removing...';
                var ts = Date.now();
                var oldHash = window.location.hash;
                window.location.hash = '#steamidra_remove_' + currentAppId + '_' + ts;
                setTimeout(function() {{ window.location.hash = oldHash; }}, 3000);
            }} else {{
                btn.innerHTML = '<span class="steamidra-spinner"></span>Adding...';
                var gameName = '';
                var titleEl = document.querySelector('.apphub_AppName') || document.querySelector('title');
                if (titleEl) gameName = (titleEl.innerText || '').replace(' on Steam', '').trim();
                var ts2 = Date.now();
                var oldHash2 = window.location.hash;
                window.location.hash = '#steamidra_add_' + currentAppId + '_' + ts2 + '|' + encodeURIComponent(gameName);
                setTimeout(function() {{ window.location.hash = oldHash2; }}, 3000);
            }}
        }}

        btn.onclick = function(e) {{ e.preventDefault(); triggerAction(); }};

        if (forController) {{
            btn.setAttribute('tabindex', '0');
            btn.classList.add('Panel', 'Focusable');
            // We do NOT add data-panel because Steam's FocusNavController will ignore raw DOM nodes anyway.

            // Focus ring — for mouse hover / click
            function onFocus() {{
                if (btn.disabled) return;
                var color = (btn.innerText && btn.innerText.includes('Remove')) ? '#ff4d4d' : '#1a9fff';
                btn.style.boxShadow = '0 0 0 4px white,0 0 0 6px ' + color;
                btn.style.transform = 'scale(1.02)';
            }}
            function onBlur() {{
                if (btn.disabled) return;
                btn.style.boxShadow = 'none';
                btn.style.transform = 'scale(1)';
            }}
            btn.addEventListener('mouseenter', onFocus);
            btn.addEventListener('mouseleave', onBlur);

            // MANUALLY HIJACK STEAM'S GAMEPAD NAVIGATION
            // Since this is a raw DOM node and not a React <Focusable>, Steam's FocusNavController
            // doesn't know it exists. We must manually catch Arrow/Gamepad directions in the capture
            // phase, manually apply Steam's .gpfocus class for the white border, and stop propagation.
            
            function onWinKeydown(e) {{
                // Steam maps controller D-pad to Arrow keys internally in CEF
                var isDown = (e.key === 'ArrowDown' || e.keyCode === 40);
                var isUp = (e.key === 'ArrowUp' || e.keyCode === 38);
                var isLeft = (e.key === 'ArrowLeft' || e.keyCode === 37);
                var isRight = (e.key === 'ArrowRight' || e.keyCode === 39);
                var isAction = (e.key === 'Enter' || e.key === ' ' || e.key === 'GamepadA');
                
                var carousel = document.getElementById('FeatureTarget_gamehighlight-gamepadcarousel');
                var hasGpFocus = btn.classList.contains('gpfocus');
                var activeNode = document.querySelector('.gpfocus') || document.activeElement;

                // 1. If our button currently has focus:
                if (hasGpFocus) {{
                    if (isAction) {{
                        e.preventDefault(); e.stopPropagation();
                        triggerAction();
                    }} else if (isUp) {{
                        e.preventDefault(); e.stopPropagation();
                        btn.classList.remove('gpfocus');
                        btn.blur();
                        onBlur(); // clear custom visual styles
                        if (carousel) {{
                            var target = carousel.querySelector('.Focusable') || carousel;
                            target.focus();
                            target.classList.add('gpfocus');
                        }}
                    }} else if (isLeft || isRight) {{
                        // Block horizontal movement so Steam doesn't desync its internal state
                        e.preventDefault(); e.stopPropagation();
                    }} else if (isDown) {{
                        // Let Steam navigate down to the next row, but clean up our fake focus
                        btn.classList.remove('gpfocus');
                        btn.blur();
                        onBlur();
                    }} else {{
                        // For Escape/Back or other navigation, just clean up our visual state
                        btn.classList.remove('gpfocus');
                        btn.blur();
                        onBlur();
                    }}
                    return;
                }}

                // 2. If our button does NOT have focus, check if we should hijack DOWN
                if (isDown && carousel && activeNode && carousel.contains(activeNode)) {{
                    e.preventDefault(); e.stopPropagation();
                    
                    // Strip gpfocus from wherever Steam had it
                    if (activeNode.classList) activeNode.classList.remove('gpfocus');
                    
                    // Force focus onto our injected DOM node
                    btn.focus();
                    btn.classList.add('gpfocus');
                    onFocus(); // trigger custom visual styles
                    return;
                }}
            }}
            
            window.addEventListener('keydown', onWinKeydown, true);

            // Cleanup: remove global listener when button is destroyed
            btn._steamidraCleanup = function() {{
                window.removeEventListener('keydown', onWinKeydown, true);
                btn.removeEventListener('mouseenter', onFocus);
                btn.removeEventListener('mouseleave', onBlur);
            }};
        }} else {{
            btn.onmouseover = function() {{ if (!btn.disabled) btn.style.opacity = '0.85'; }};
            btn.onmouseout  = function() {{ if (!btn.disabled) btn.style.opacity = '1'; }};
        }}

        return btn;
    }}

    // Helper: run cleanup and remove element
    function cleanupEl(id) {{
        var el = document.getElementById(id);
        if (el) {{
            if (el._steamidraCleanup) el._steamidraCleanup();
            el.remove();
        }}
    }}

    // Permanent self-healing interval — checks every 500ms.
    // Exits early (fast-path) if URL is unchanged AND both buttons are present.
    var _lastUrl = '';
    var STORE_RE = /store\\.steampowered\\.com\\/app\\/\\d+/i;

    setInterval(function() {{
        var currentUrl = window.location.href.split('#')[0];
        var isStorePage = STORE_RE.test(currentUrl);

        var hasNormal = !!document.getElementById('steamidra-btn-normal');
        var hasBP     = !!document.getElementById('steamidra-wrapper-bp');

        // Fast-path: URL unchanged, page is a store page, both buttons present
        if (currentUrl === _lastUrl && isStorePage && hasNormal && hasBP) return;

        if (!isStorePage) {{
            // Navigated away — clean up any lingering buttons
            if (hasNormal || hasBP) {{
                cleanupEl('steamidra-btn-normal');
                cleanupEl('steamidra-wrapper-bp');
                cleanupEl('steamidra-wrapper-bp');
            }}
            _lastUrl = currentUrl;
            return;
        }}

        _lastUrl = currentUrl;

        // Normal store mode
        if (!hasNormal) {{
            var normalContainer = document.querySelector('.apphub_HeaderStandardTop');
            if (normalContainer) {{
                var btn1 = makeBtn('steamidra-btn-normal', false);
                if (btn1) normalContainer.appendChild(btn1);
            }}
        }}

        // Big Picture mode
        if (!hasBP) {{
            var bpContainer = document.getElementById('FeatureTarget_gamehighlight-gamepadcarousel');
            if (bpContainer) {{
                var btn2 = makeBtn('steamidra-wrapper-bp', true);
                if (btn2) {{
                    bpContainer.appendChild(btn2);
                }}
            }}
        }}
    }}, 500);

}})();
"""


def get_app_id_from_url(url):
    """Extract app ID from store.steampowered.com/app/{id}/... URLs."""
    m = re.search(r'store\.steampowered\.com/app/(\d+)', url)
    return m.group(1) if m else None


def get_steam_exe():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam_path = winreg.QueryValueEx(key, "SteamExe")[0]
            return Path(steam_path).resolve()
    except Exception:
        return Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")) / "Steam" / "steam.exe"


def ensure_steam_debugging():
    try:
        requests.get("http://localhost:8080/json", timeout=2)
        return True
    except Exception:
        pass

    logger.info("Restarting Steam with debugging enabled...")
    subprocess.run(["taskkill", "/F", "/IM", "steam.exe"], capture_output=True)
    subprocess.run(["taskkill", "/F", "/IM", "steamwebhelper.exe"], capture_output=True)
    time.sleep(2)  # Give OS time to release file locks

    steam_exe = get_steam_exe()
    if steam_exe.exists():
        subprocess.Popen(
            [str(steam_exe), "-cef-enable-debugging", "-cef-port=8080"],
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        )
        time.sleep(5)
        return True
    return False


def inject_popup(tab_id, app_id=None):
    """Inject the SteaMidra button into a Steam store tab.
    app_id is the numeric string for the current page; if provided, the library
    state is looked up here in Python and embedded into the JS so the button
    shows 'Remove from Library' for already-added games.
    """
    try:
        library_ids = get_library_app_ids()
    except Exception as e:
        logger.debug("inject_popup: library scan failed, defaulting to empty: %s", e)
        library_ids = set()

    js_code = _build_js_popup(library_ids)
    ws_url = f"ws://localhost:8080/devtools/page/{tab_id}"
    try:
        ws = create_connection(ws_url, timeout=10)
        ws.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": js_code}
        }))
        ws.recv()
        ws.close()
        mode = "remove" if (app_id and app_id in library_ids) else "add"
        logger.info(f"Popup injected into tab {tab_id} (app_id={app_id}, mode={mode})")
    except Exception as e:
        logger.error(f"Failed to inject popup: {e}")


def update_steam_ui(tab_id, js_code):
    ws_url = f"ws://localhost:8080/devtools/page/{tab_id}"
    try:
        ws = create_connection(ws_url, timeout=5)
        ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate", "params": {"expression": js_code}}))
        ws.recv()
        ws.close()
    except Exception as e:
        logger.error(f"Failed to update UI in tab {tab_id}: {e}")


def show_toast(tab_id, message):
    js = f"""
    var t = document.createElement('div');
    t.innerText = {json.dumps(message)};
    t.style.cssText = 'position:fixed;bottom:20px;right:20px;background:#1a9fff;color:white;padding:15px 25px;border-radius:5px;box-shadow:0 4px 12px rgba(0,0,0,0.5);z-index:999999;font-weight:bold;font-family:Arial,sans-serif;';
    document.body.appendChild(t);
    setTimeout(function() {{ t.remove(); }}, 5000);
    """
    update_steam_ui(tab_id, js)


def injection_loop(ui_ref):
    if not ensure_steam_debugging():
        return

    from urllib.parse import unquote
    from PyQt6.QtCore import QMetaObject, Qt, Q_ARG

    # Track last injected URL per tab to avoid duplicate injections for the same navigation.
    # Capped at 50 entries to prevent unbounded memory growth across long sessions.
    last_injected: dict[str, str] = {}

    def check_and_inject(tab_id, url):
        if not tab_id or not url:
            return

        def set_last(key, val):
            if len(last_injected) >= 50:
                try:
                    last_injected.pop(next(iter(last_injected)))
                except StopIteration:
                    pass
            last_injected[key] = val

        # Button click hook — hash signals a game add request from the JS
        if "#steamidra_add_" in url:
            if url == last_injected.get(tab_id + "_signal"):
                return
            set_last(tab_id + "_signal", url)
            m = re.search(r'#steamidra_add_(\d+)_\d+(?:\|([^#]+))?', url)
            if m and ui_ref:
                app_id = m.group(1)
                game_name = unquote(m.group(2)) if m.group(2) else ""
                logger.info(f"Steam UI requested download for {app_id} ({game_name}) in tab {tab_id}")
                QMetaObject.invokeMethod(
                    ui_ref, "run_injector_add",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, app_id), Q_ARG(str, tab_id), Q_ARG(str, game_name)
                )
            return

        # Button click hook — hash signals a game remove request from the JS
        if "#steamidra_remove_" in url:
            if url == last_injected.get(tab_id + "_signal"):
                return
            set_last(tab_id + "_signal", url)
            m = re.search(r'#steamidra_remove_(\d+)_\d+', url)
            if m and ui_ref:
                app_id = m.group(1)
                logger.info(f"Steam UI requested removal for {app_id} in tab {tab_id}")
                QMetaObject.invokeMethod(
                    ui_ref, "run_injector_remove",
                    Qt.ConnectionType.QueuedConnection,
                    Q_ARG(str, app_id), Q_ARG(str, tab_id)
                )
            return

        app_id = get_app_id_from_url(url)
        clean_url = url.split('#')[0]
        if app_id and last_injected.get(tab_id) != clean_url:
            set_last(tab_id, clean_url)
            threading.Thread(target=inject_popup, args=(tab_id, app_id), daemon=True).start()

    # Step 1: inject into any already-open store tabs immediately
    try:
        tabs = requests.get("http://localhost:8080/json", timeout=2).json()
        for tab in tabs:
            check_and_inject(tab.get("id", ""), tab.get("url", ""))
    except Exception as e:
        logger.error(f"Initial scan failed: {e}")

    # Step 2: poll every tab's URL (via per-tab CDP evaluate) so we catch
    # hash-only navigations (#steamidra_add_ / #steamidra_remove_) that the
    # browser-level Target.targetInfoChanged completely misses.
    POLL_INTERVAL = 0.5  # seconds
    while True:
        try:
            tabs = requests.get("http://localhost:8080/json", timeout=2).json()
        except Exception as e:
            logger.error(f"CDP poll failed: {e} — retrying in 3s")
            time.sleep(3)
            continue

        for tab in tabs:
            tab_id = tab.get("id", "")
            if not tab_id:
                continue
            # Fast path: use URL from /json if it has no hash (no signal pending)
            reported_url = tab.get("url", "")
            if "#steamidra_" not in reported_url:
                # Also do the normal inject check on this reported URL
                check_and_inject(tab_id, reported_url)
                continue

            # Hash signal detected in /json URL — process it directly
            check_and_inject(tab_id, reported_url)

            # Also evaluate actual live URL in the tab so we catch signals that
            # /json hasn't yet reflected (race window between set and clear)
            try:
                ws_url = f"ws://localhost:8080/devtools/page/{tab_id}"
                ws2 = create_connection(ws_url, timeout=3)
                ws2.send(json.dumps({
                    "id": 99,
                    "method": "Runtime.evaluate",
                    "params": {"expression": "window.location.href"}
                }))
                resp = json.loads(ws2.recv())
                ws2.close()
                live_url = resp.get("result", {}).get("result", {}).get("value", "")
                if live_url and live_url != reported_url:
                    check_and_inject(tab_id, live_url)
            except Exception:
                pass

        time.sleep(POLL_INTERVAL)




def start_injector(ui_ref=None):
    t = threading.Thread(target=injection_loop, args=(ui_ref,), daemon=True)
    t.start()

