import json
import threading
import time
import requests
try:
    import websocket
except Exception as e:
    raise ImportError("Missing websocket module. Please install 'websocket-client' (pip install websocket-client)") from e

if not hasattr(websocket, 'WebSocketApp'):
    raise ImportError(
        "The imported 'websocket' module doesn't provide WebSocketApp.\n"
        "This often happens when a conflicting package named 'websocket' is installed.\n"
        "Fix: pip uninstall websocket && pip install websocket-client"
    )

from Scripts.Utils import dict_result, get_config_path, get_user_info

LOGIN_WSS_URL = "wss://pro.yuketang.cn/wsapp/"


def login_via_qrcode(config):
    """Display QR code in terminal, wait for WeChat scan, return True on success."""
    login_success = threading.Event()
    sessionid_holder = {}

    def on_open(wsapp):
        data = {"op": "requestlogin", "role": "web", "version": 1.4, "type": "qrcode", "from": "web"}
        wsapp.send(json.dumps(data))

    def on_close(wsapp):
        pass

    def on_message(wsapp, message):
        data = dict_result(message)
        if data["op"] == "requestlogin":
            ticket_url = data["ticket"]
            _print_qrcode(ticket_url)
        elif data["op"] == "loginsuccess":
            web_login_url = "https://pro.yuketang.cn/pc/web_login"
            login_data = json.dumps({
                "UserID": data["UserID"],
                "Auth": data["Auth"]
            })
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:104.0) Gecko/20100101 Firefox/104.0"
            }
            r = requests.post(url=web_login_url, data=login_data, headers=headers,
                            proxies={"http": None, "https": None})
            sessionid = dict(r.cookies)["sessionid"]
            sessionid_holder["sessionid"] = sessionid
            login_success.set()

    wsapp = websocket.WebSocketApp(url=LOGIN_WSS_URL, on_open=on_open, on_message=on_message, on_close=on_close)

    # Start WebSocket thread
    ws_thread = threading.Thread(target=wsapp.run_forever, daemon=True)
    ws_thread.start()

    # QR refresh thread (every 60 seconds)
    flush_stop = threading.Event()

    def flush_qr():
        count = 0
        while not flush_stop.is_set() and not login_success.is_set():
            if count >= 60:
                count = 0
                try:
                    data = {"op": "requestlogin", "role": "web", "version": 1.4, "type": "qrcode", "from": "web"}
                    wsapp.send(json.dumps(data))
                except Exception:
                    break
            else:
                time.sleep(1)
                count += 1

    flush_thread = threading.Thread(target=flush_qr, daemon=True)
    flush_thread.start()

    print("\n请使用微信扫描二维码登录荷塘雨课堂...\n")
    print("（二维码每60秒自动刷新，按 Ctrl+C 取消登录）\n")

    try:
        login_success.wait(timeout=300)  # 5 minutes timeout
    except KeyboardInterrupt:
        print("\n登录已取消")
        flush_stop.set()
        wsapp.close()
        ws_thread.join(timeout=2)
        flush_thread.join(timeout=2)
        return False

    flush_stop.set()
    wsapp.close()
    ws_thread.join(timeout=2)
    flush_thread.join(timeout=2)

    if sessionid_holder.get("sessionid"):
        sessionid = sessionid_holder["sessionid"]
        config["sessionid"] = sessionid
        _save_config(config)

        # Verify login
        code, user_info = get_user_info(sessionid)
        if code == 0:
            print(f"\n登录成功！当前用户：{user_info.get('name', '未知')}")
            return True
        else:
            print("\n登录验证失败，请重试")
            return False
    else:
        print("\n登录超时，请重试")
        return False


def _print_qrcode(ticket_url):
    """Render QR code from ticket URL in terminal."""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(ticket_url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
    except ImportError:
        # Fallback: just print the URL
        print(f"\n请访问以下链接（需要安装 qrcode 库以获得更好的体验）：\n{ticket_url}\n")
    except Exception:
        print(f"\n二维码渲染失败，请访问链接：\n{ticket_url}\n")


def _save_config(config):
    """Save config to file."""
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
