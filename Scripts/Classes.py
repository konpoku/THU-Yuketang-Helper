import requests
import threading
import time
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
import json
from Scripts.Utils import dict_result

wss_url = "wss://pro.yuketang.cn/wsapp/"


class Lesson:
    def __init__(self, lessonid, lessonname, classroomid, sessionid, log_callback=None, notify_callback=None):
        self.classroomid = classroomid
        self.lessonid = lessonid
        self.lessonname = lessonname
        self.sessionid = sessionid
        self.headers = {
            "Cookie": "sessionid=%s" % self.sessionid,
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:97.0) Gecko/20100101 Firefox/97.0",
        }
        self.problems_ls = []
        self.log = log_callback or (lambda msg, typ: None)
        self.notify = notify_callback or (lambda lesson_name, problem_info: None)

        r = requests.get(url="https://pro.yuketang.cn/api/v3/user/basic-info", headers=self.headers,
                        proxies={"http": None, "https": None})
        rtn = dict_result(r.text)
        if rtn["code"] == 0:
            self.user_uid = rtn["data"]["id"]
            self.user_uname = rtn["data"]["name"]
        else:
            self.user_uid = ""
            self.user_uname = ""

    def _get_ppt(self, presentationid):
        r = requests.get(
            url="https://pro.yuketang.cn/api/v3/lesson/presentation/fetch?presentation_id=%s" % presentationid,
            headers=self.headers, proxies={"http": None, "https": None})
        return dict_result(r.text)["data"]

    def get_problems(self, presentationid):
        data = self._get_ppt(presentationid)
        return [problem["problem"] for problem in data["slides"] if "problem" in problem.keys()]

    def on_open(self, wsapp):
        self.handshake = {"op": "hello", "userid": self.user_uid, "role": "student", "auth": self.auth,
                         "lessonid": self.lessonid}
        wsapp.send(json.dumps(self.handshake))

    def checkin_class(self):
        r = requests.post(url="https://pro.yuketang.cn/api/v3/lesson/checkin", headers=self.headers,
                        data=json.dumps({"source": 5, "lessonId": self.lessonid}),
                        proxies={"http": None, "https": None})
        set_auth = r.headers.get("Set-Auth", None)
        times = 1
        while not set_auth and times <= 3:
            set_auth = r.headers.get("Set-Auth", None)
            times += 1
            time.sleep(1)
        self.headers["Authorization"] = "Bearer %s" % set_auth
        return dict_result(r.text)["data"]["lessonToken"]

    def on_message(self, wsapp, message):
        data = dict_result(message)
        op = data["op"]
        if op == "hello":
            presentations = list(set([slide["pres"] for slide in data.get("timeline", []) if slide["type"] == "slide"]))
            current_presentation = data.get("presentation")
            if current_presentation and current_presentation not in presentations:
                presentations.append(current_presentation)
            for presentationid in presentations:
                self.problems_ls.extend(self.get_problems(presentationid))
            # Query info for already-unlocked problems
            for problemid in data.get("unlockedproblem", []):
                self._query_problem(wsapp, problemid)
        elif op == "unlockproblem":
            problem = data["problem"]
            self.log("%s 检测到新习题" % self.lessonname, 3)
            # Send Feishu notification
            self.notify(self.lessonname, {
                "problemId": problem["sid"],
                "problemType": problem.get("problemType", 0),
                "limit": problem.get("limit", -1),
                "body": problem.get("body", ""),
                "answers": problem.get("answers", []),
                "blanks": problem.get("blanks", []),
            })
        elif op == "lessonfinished":
            self.log("%s 下课了" % self.lessonname, 7)
            wsapp.close()
        elif op == "presentationupdated" or op == "presentationcreated":
            self.problems_ls.extend(self.get_problems(data["presentation"]))
        elif op == "callpaused":
            msg = "%s 点名了，点到了：%s" % (self.lessonname, data["name"])
            if self.user_uname == data["name"]:
                self.log(msg, 5)
            else:
                self.log(msg, 6)
        elif op == "probleminfo":
            # Problem info received — also notify via Feishu
            problem_type = data.get("problemType", 0)
            problem_id = data.get("problemid", "")
            body = data.get("body", "")
            answers = data.get("answers", [])
            blanks = data.get("blanks", [])
            if data["limit"] != -1:
                time_left = int(data["limit"] - (int(data["now"]) - int(data["dt"])) / 1000)
            else:
                time_left = data["limit"]

            if time_left > 0 or time_left == -1:
                self.log("%s 检测到习题" % self.lessonname, 3)
                self.notify(self.lessonname, {
                    "problemId": problem_id,
                    "problemType": problem_type,
                    "limit": time_left if time_left != -1 else -1,
                    "body": body,
                    "answers": answers,
                    "blanks": blanks,
                })

                if time_left == -1:
                    self.log("%s 该题不限时，请尽快前往荷塘雨课堂回答" % self.lessonname, 3)
                else:
                    self.log("%s 请在 %s 秒内前往荷塘雨课堂回答" % (self.lessonname, time_left), 3)

    def _query_problem(self, wsapp, problemid):
        query = {"op": "probleminfo", "lessonid": self.lessonid, "problemid": problemid, "msgid": 1}
        wsapp.send(json.dumps(query))

    def start_lesson(self, callback=None):
        self.auth = self.checkin_class()
        rtn = self.get_lesson_info()
        teacher = rtn["teacher"]["name"]
        title = rtn["title"]
        timestamp = rtn["startTime"] // 1000
        time_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
        self.log("%s | 课程：%s | 教师：%s | 上课时间：%s" % (self.lessonname, title, teacher, time_str), 7)
        self.wsapp = websocket.WebSocketApp(url=wss_url, header=self.headers,
                                           on_open=self.on_open, on_message=self.on_message)
        self.wsapp.run_forever()
        self.log("%s 监听结束" % self.lessonname, 7)
        if callback:
            return callback(self)

    def get_lesson_info(self):
        url = "https://pro.yuketang.cn/api/v3/lesson/basic-info"
        r = requests.get(url=url, headers=self.headers, proxies={"http": None, "https": None})
        return dict_result(r.text)["data"]

    def __eq__(self, other):
        return self.lessonid == other.lessonid
