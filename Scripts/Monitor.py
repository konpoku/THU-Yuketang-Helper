import time
import requests
import threading
from Scripts.Utils import get_on_lesson, test_network
from Scripts.Classes import Lesson


def monitor(sessionid, log_callback=None, notify_callback=None, stop_event=None):
    """Start the monitoring loop. Returns the stop_event for external control."""

    if stop_event is None:
        stop_event = threading.Event()

    log = log_callback or (lambda msg, typ: None)

    def del_onclass(lesson_obj):
        on_lesson_list.remove(lesson_obj)

    on_lesson_list = []
    lesson_list = []
    network_status = True

    while not stop_event.is_set():
        # Get current lesson list
        try:
            lesson_list = get_on_lesson(sessionid)
        except requests.exceptions.ConnectionError:
            log("网络异常，监听中断", 8)
            network_status = False
        except Exception:
            pass

        # Network recovery handling
        while not network_status and not stop_event.is_set():
            ret = test_network()
            if ret:
                try:
                    lesson_list = get_on_lesson(sessionid)
                except Exception:
                    pass
                else:
                    network_status = True
                    log("网络已恢复，监听开始", 8)
                    break
            # Wait 5s, checking stop_event each second
            for _ in range(5):
                if stop_event.is_set():
                    for lesson in on_lesson_list.copy():
                        try:
                            lesson.wsapp.close()
                        except Exception:
                            pass
                    return stop_event
                time.sleep(1)

        # Process current lessons
        for lesson in lesson_list:
            lessonid = lesson["lessonId"]
            lessonname = lesson["courseName"]
            classroomid = lesson["classroomId"]
            lesson_obj = Lesson(lessonid, lessonname, classroomid, sessionid,
                              log_callback=log, notify_callback=notify_callback)
            if lesson_obj not in on_lesson_list:
                thread = threading.Thread(target=lesson_obj.start_lesson, args=(del_onclass,), daemon=True)
                thread.start()
                log("检测到课程 %s 正在上课，已加入监听列表" % lessonname, 7)
                on_lesson_list.append(lesson_obj)

        # Wait 10s, checking stop_event each second
        for _ in range(10):
            if stop_event.is_set():
                for lesson in on_lesson_list.copy():
                    try:
                        lesson.wsapp.close()
                    except Exception:
                        pass
                return stop_event
            time.sleep(1)

    # Cleanup on stop
    for lesson in on_lesson_list.copy():
        try:
            lesson.wsapp.close()
        except Exception:
            pass
    return stop_event
