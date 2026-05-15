#!/usr/bin/env python3
"""荷塘雨课堂 CLI 助手 — 监听课程新习题并通过飞书 Webhook 通知"""

import argparse
import datetime
import json
import os
import signal
import sys
import threading
import warnings

warnings.filterwarnings("ignore", message="urllib3 v2 only supports OpenSSL")

from Scripts.Utils import (
    get_config_path, get_config_dir,
    get_initial_data, get_user_info, get_on_lesson
)
from Scripts.login import login_via_qrcode
from Scripts.Monitor import monitor
from Scripts.feishu import send_feishu_notification, send_feishu_text


def load_config():
    config_dir = get_config_dir()
    config_path = get_config_path()
    if not os.path.exists(config_dir):
        os.makedirs(config_dir, exist_ok=True)
    if not os.path.exists(config_path):
        initial_data = get_initial_data()
        with open(config_path, "w") as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        return initial_data
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except Exception:
        initial_data = get_initial_data()
        with open(config_path, "w") as f:
            json.dump(initial_data, f, indent=2, ensure_ascii=False)
        return initial_data


def save_config(config):
    config_path = get_config_path()
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)


def make_logger(webhook_url=None):
    def log(msg, msg_type=0):
        timestamp = datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S] ")
        print(timestamp + msg)
        if webhook_url and msg_type in (3, 5, 6):
            send_feishu_text(webhook_url, msg)
    return log


def make_notifier(webhook_url):
    if not webhook_url:
        return None
    def notify(lesson_name, problem_info):
        send_feishu_notification(webhook_url, lesson_name, problem_info)
    return notify


def cmd_login(args, config):
    if not login_via_qrcode(config):
        print("登录失败")
        sys.exit(1)


def cmd_start(args, config):
    sessionid = config.get("sessionid", "")
    if not sessionid:
        print("未检测到登录状态，正在启动登录流程...")
        if not login_via_qrcode(config):
            print("登录失败，无法启动监听")
            sys.exit(1)
        sessionid = config.get("sessionid", "")

    code, user_info = get_user_info(sessionid)
    if code != 0:
        print("登录状态已失效，请重新登录")
        if not login_via_qrcode(config):
            print("登录失败，无法启动监听")
            sys.exit(1)
        sessionid = config.get("sessionid", "")
        code, user_info = get_user_info(sessionid)
        if code != 0:
            print("登录验证失败")
            sys.exit(1)

    print(f"\n已登录，当前用户：{user_info.get('name', '未知')}")

    webhook_url = args.webhook or config.get("feishu_webhook_url", "")
    if not webhook_url:
        print("\n提示：未设置飞书 Webhook URL，将不会发送飞书通知。")
        print("使用方法：python main.py start --webhook <URL>")
        print("或设置：python main.py config set feishu_webhook_url <URL>\n")
    else:
        print(f"飞书通知：已启用")

    print("\n开始监听... 按 Ctrl+C 停止\n")

    log = make_logger(webhook_url)
    notify = make_notifier(webhook_url)
    stop_event = threading.Event()

    def signal_handler(sig, frame):
        print("\n正在停止监听...")
        stop_event.set()

    signal.signal(signal.SIGINT, signal_handler)

    try:
        monitor(sessionid, log_callback=log, notify_callback=notify, stop_event=stop_event)
    except KeyboardInterrupt:
        pass

    print("监听已停止")


def cmd_status(args, config):
    sessionid = config.get("sessionid", "")
    if not sessionid:
        print("状态：未登录")
        print("使用方法：python main.py login")
        return

    code, user_info = get_user_info(sessionid)
    if code == 0:
        print(f"状态：已登录")
        print(f"用户：{user_info.get('name', '未知')}")
        print(f"学校：{user_info.get('school', '未知')}")
        print(f"学号：{user_info.get('sno', '未知')}")

        try:
            lessons = get_on_lesson(sessionid)
            if lessons:
                print(f"\n当前正在上课的课程 ({len(lessons)})：")
                for lesson in lessons:
                    print(f"  - {lesson.get('courseName', '未知')} (ID: {lesson.get('lessonId', '')})")
            else:
                print("\n当前没有正在上课的课程")
        except Exception as e:
            print(f"\n获取课程列表失败：{e}")
    else:
        print("状态：登录已过期，请重新登录：python main.py login")

    webhook_url = config.get("feishu_webhook_url", "")
    print(f"\n飞书通知：{'已配置' if webhook_url else '未配置'}")
    if webhook_url:
        print(f"Webhook URL: {webhook_url}")


def cmd_config(args, config):
    if args.config_action == "show":
        print("当前配置：")
        sessionid = config.get("sessionid", "")
        print(f"  sessionid: {sessionid[:20]}{'...' if len(sessionid) > 20 else ''}")
        print(f"  feishu_webhook_url: {config.get('feishu_webhook_url', '')}")
    elif args.config_action == "set":
        if not args.key:
            print("用法：python main.py config set <key> <value>")
            print("可用 key: feishu_webhook_url")
            return
        key = args.key
        value = args.value

        if key == "feishu_webhook_url":
            config["feishu_webhook_url"] = value
        else:
            print(f"未知配置项：{key}")
            return

        save_config(config)
        print(f"已设置 {key} = {value}")


def main():
    parser = argparse.ArgumentParser(
        description="荷塘雨课堂 CLI 助手 — 监听课程新习题并通过飞书 Webhook 通知",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python main.py login                    # 终端二维码登录
  python main.py start                    # 开始监听
  python main.py start --webhook <URL>    # 开始监听并通过飞书通知
  python main.py status                   # 查看登录状态和课程
  python main.py config show              # 查看当前配置
  python main.py config set feishu_webhook_url <URL>  # 设置飞书 Webhook
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="可用命令")

    subparsers.add_parser("login", help="通过终端二维码登录荷塘雨课堂")

    start_parser = subparsers.add_parser("start", help="开始监听课程")
    start_parser.add_argument("--webhook", type=str, help="飞书 Bot Webhook URL")

    subparsers.add_parser("status", help="查看登录状态和当前课程")

    config_parser = subparsers.add_parser("config", help="查看或修改配置")
    config_sub = config_parser.add_subparsers(dest="config_action", help="操作")
    config_sub.add_parser("show", help="显示当前配置")
    set_parser = config_sub.add_parser("set", help="设置配置项")
    set_parser.add_argument("key", type=str, help="配置项名称")
    set_parser.add_argument("value", type=str, help="配置项值")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    config = load_config()

    if args.command == "login":
        cmd_login(args, config)
    elif args.command == "start":
        cmd_start(args, config)
    elif args.command == "status":
        cmd_status(args, config)
    elif args.command == "config":
        cmd_config(args, config)


if __name__ == "__main__":
    main()
