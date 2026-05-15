# 荷塘雨课堂助手

去掉了GUI及其依赖，完全可以在CLI中运行的简化版雨课堂助手。并且添加了通过飞书通知有新习题的功能

## 功能

- **自动签到** — 课程开始时自动签到
- **习题监控** — 实时检测课堂上发布的新习题（单选、多选、填空、主观题、投票题）
- **飞书通知** — 检测到新习题时，通过飞书 Webhook 机器人推送提醒到手机
- **点名提醒** — 检测到点名时在终端提示
- **多课程支持** — 同时监听多个正在上课的课程
- **跨平台** — 支持 macOS 和 Windows

## 使用方法

### 1. 登录

终端内显示二维码，使用微信扫码登录荷塘雨课堂：

```bash
python main.py login
```

### 2. 开始监听

```bash
# 仅终端输出
python main.py start

# 同时通过飞书 Bot 推送习题提醒
python main.py start --webhook <飞书机器人Webhook URL>
```

监听启动后，程序会通过 WebSocket 实时监控所有正在上课的课程。检测到新习题时，终端会显示题目信息；若配置了飞书 Webhook，还会推送一张包含题型、时限、题目内容和选项的卡片消息。

按 `Ctrl+C` 停止监听。

### 3. 查看状态

```bash
python main.py status
```

显示当前登录状态、用户信息、正在上课的课程列表，以及飞书通知配置情况。

### 4. 配置管理

```bash
# 查看当前配置
python main.py config show

# 设置飞书 Webhook URL（持久化保存）
python main.py config set feishu_webhook_url <URL>
```

## 获取飞书 Webhook URL

1. 打开飞书，进入目标群组
2. 群设置 → 群机器人 → 添加机器人 → 自定义机器人
3. 设置安全配置（建议使用"签名校验"以外的免校验方式）
4. 复制 Webhook URL

## 项目结构

```
├── main.py                 # CLI 入口
├── Scripts/
│   ├── login.py            # 终端二维码登录
│   ├── Classes.py          # 课程 WebSocket 连接与消息处理
│   ├── Monitor.py          # 多课程监听调度
│   ├── Utils.py            # 网络请求、配置读写等工具函数
│   └── feishu.py           # 飞书 Webhook 通知（卡片消息 + 文本消息）
└── requirements.txt
```