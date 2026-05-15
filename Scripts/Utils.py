import json
import requests
import os
import sys


def dict_result(text):
    return dict(json.loads(text))


def test_network():
    try:
        requests.get("https://baidu.com", timeout=5)
        return True
    except Exception:
        return False


def get_initial_data():
    return {
        "sessionid": "",
        "feishu_webhook_url": "",
    }


def get_config_path():
    config_dir = get_config_dir()
    return os.path.join(config_dir, "config.json")


def get_config_dir():
    try:
        if 'APPDATA' in os.environ:
            appdata_route = os.environ['APPDATA']
            dir_route = os.path.join(appdata_route, 'RainClassroomAssistant')
        else:
            if sys.platform == 'darwin':
                base = os.path.expanduser('~/Library/Application Support')
            else:
                base = os.environ.get('XDG_CONFIG_HOME', os.path.expanduser('~/.config'))
            dir_route = os.path.join(base, 'RainClassroomAssistant')

        if not os.path.exists(dir_route):
            try:
                os.makedirs(dir_route, exist_ok=True)
            except Exception:
                dir_route = os.path.abspath('.')
        return dir_route
    except Exception:
        return os.path.abspath('.')


def get_user_info(sessionid):
    headers = {
        "Cookie": "sessionid=%s" % sessionid,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
    }
    r = requests.get(url="https://pro.yuketang.cn/api/v3/user/basic-info", headers=headers,
                    proxies={"http": None, "https": None})
    rtn = dict_result(r.text)
    return (rtn["code"], rtn["data"])


def get_on_lesson(sessionid):
    headers = {
        "Cookie": "sessionid=%s" % sessionid,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
    }
    r = requests.get("https://pro.yuketang.cn/api/v3/classroom/on-lesson", headers=headers,
                    proxies={"http": None, "https": None})
    rtn = dict_result(r.text)
    return rtn["data"]["onLessonClassrooms"]
