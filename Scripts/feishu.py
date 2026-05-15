import requests
import json

# Problem type mapping
PROBLEM_TYPE_MAP = {
    1: "单选题",
    2: "多选题",
    3: "填空题",
    4: "主观题",
    5: "投票题",
}

FEISHU_COLORS = {
    "info": "blue",
    "warning": "yellow",
    "error": "red",
    "success": "green",
}

def send_feishu_notification(webhook_url, lesson_name, problem_info):
    """Send a rich card notification to Feishu when a new problem is detected."""
    problem_type = problem_info.get("problemType", 0)
    type_name = PROBLEM_TYPE_MAP.get(problem_type, "未知类型")
    problem_id = problem_info.get("problemId", "")
    time_limit = problem_info.get("limit", -1)
    body = problem_info.get("body", "")

    if time_limit == -1:
        limit_text = "不限时"
    else:
        limit_text = f"{time_limit}秒"

    # Build card content
    elements = []
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**课程：**{lesson_name}"}
    })
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**题型：**{type_name}"}
    })
    elements.append({
        "tag": "div",
        "text": {"tag": "lark_md", "content": f"**时限：**{limit_text}"}
    })
    if body:
        # Truncate long bodies
        body_display = body[:200] + "..." if len(body) > 200 else body
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**题目：**{body_display}"}
        })

    # Show answer options for choice questions
    answers = problem_info.get("answers", [])
    if answers:
        options_text = "\n".join(f"• {a}" for a in answers[:10])
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**选项：**\n{options_text}"}
        })

    # Show blank info for fill-in-the-blank
    blanks = problem_info.get("blanks", [])
    if blanks:
        blanks_info = "\n".join(f"第{b.get('index', i+1)}空: {', '.join(b.get('answers', []))}" for i, b in enumerate(blanks[:5]))
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": f"**填空选项：**\n{blanks_info}"}
        })

    elements.append({
        "tag": "hr"
    })
    elements.append({
        "tag": "note",
        "elements": [{"tag": "plain_text", "content": f"Problem ID: {problem_id}"}]
    })

    payload = {
        "msg_type": "interactive",
        "card": {
            "header": {
                "title": {"tag": "plain_text", "content": "📝 新习题提醒"},
                "template": FEISHU_COLORS["warning"]
            },
            "elements": elements
        }
    }

    _send_to_feishu(webhook_url, payload)


def send_feishu_text(webhook_url, message):
    """Send a simple text message to Feishu webhook."""
    payload = {
        "msg_type": "text",
        "content": {
            "text": message
        }
    }
    _send_to_feishu(webhook_url, payload)


def send_feishu_network_status(webhook_url, status, detail=""):
    """Send network status change notification."""
    if status == "disconnected":
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "⚠️ 网络异常"},
                    "template": FEISHU_COLORS["error"]
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"监听的网络连接已断开\n{detail}"}}
                ]
            }
        }
    elif status == "recovered":
        payload = {
            "msg_type": "interactive",
            "card": {
                "header": {
                    "title": {"tag": "plain_text", "content": "✅ 网络已恢复"},
                    "template": FEISHU_COLORS["success"]
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": f"网络连接已恢复正常\n{detail}"}}
                ]
            }
        }
    _send_to_feishu(webhook_url, payload)


def _send_to_feishu(webhook_url, payload):
    """Internal: send POST to Feishu webhook."""
    try:
        headers = {"Content-Type": "application/json"}
        r = requests.post(webhook_url, data=json.dumps(payload), headers=headers, timeout=10)
        result = r.json()
        if result.get("code") != 0:
            print(f"[飞书通知失败] code={result.get('code')}, msg={result.get('msg')}")
    except Exception as e:
        print(f"[飞书通知异常] {e}")
