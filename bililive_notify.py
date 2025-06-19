import requests
import json
import time

CONFIG_FILE = "config.json"

HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"),
    "Referer": "https://live.bilibili.com/",
    "Accept": "application/json",
    "Connection": "keep-alive",
}

def load_config():
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "bark_url": "",
            "uids": [],
            "users": {},
            "live_status": {}
        }

def save_config(config):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=4)

def update_user_info(uid):
    url = "https://api.live.bilibili.com/live_user/v1/Master/info"
    try:
        resp = requests.get(url, params={"uid": uid}, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 and "info" in data.get("data", {}):
            info = data["data"]["info"]
            follower_num = data["data"].get("follower_num", 0)
            user_data = {
                "uname": info.get("uname", ""),
                "face": info.get("face", ""),
                "follower_num": follower_num
            }
            print(f"更新用户信息成功: {user_data}")
            return user_data
        else:
            print(f"更新用户信息失败: {uid} - {data.get('message')}")
    except Exception as e:
        print(f"请求用户信息异常: {uid} - {e}")
    return None

def get_live_status_info(uids):
    """
    使用 API 获取 UID 的直播状态信息
    """
    url = "https://api.live.bilibili.com/room/v1/Room/get_status_info_by_uids"
    params = [("uids[]", str(uid)) for uid in uids]
    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 and "data" in data:
            return data["data"]
        else:
            print(f"获取直播状态失败: {data.get('message')}")
    except Exception as e:
        print(f"请求直播状态异常: {e}")
    return {}

def send_bark_notification(message, icon_url, bark_url, live_count):
    if not bark_url:
        print("BARK_URL 未配置，无法推送消息")
        return
    payload = {
        "title": f"【Live通知】当前{live_count}人直播中",
        "body": message,
        "sound": "healthnotification",
        "icon": icon_url or "",
    }
    try:
        resp = requests.post(bark_url, json=payload, timeout=10)
        resp.raise_for_status()
        print("推送消息成功")
    except Exception as e:
        print(f"推送消息失败: {e}")

def main():
    config = load_config()
    bark_url = config.get("bark_url", "").strip()
    uids = config.get("uids", [])
    users = config.get("users", {})
    live_status = config.get("live_status", {})

    if not uids:
        print("配置中 uids 为空，退出")
        return

    # 获取直播状态信息
    live_infos = get_live_status_info(uids)

    live_messages = []
    first_live_icon = None
    any_live_now = False  # 标记当前是否有直播中
    live_status_new = live_status.copy()

    # 依次处理每个 UID
    live_hosts = []
    for uid in uids:
        uid_str = str(uid)
        info = live_infos.get(uid_str)
        if not info:
            # 该主播接口无返回，默认未直播
            live_status_new[uid_str] = 0
            continue

        live_state = info.get("live_status", 0)
        title = info.get("title", "")
        uname = info.get("uname", "")

        # 更新用户信息，如果用户不存在或粉丝数为0，则更新一次（避免没数据）
        user = users.get(uid_str)
        if user is None or user.get("follower_num", 0) == 0:
            user_data = update_user_info(uid)
            if user_data:
                users[uid_str] = user_data
                user = user_data
            else:
                user = {"uname": uname, "face": "", "follower_num": 0}

        any_live_now = any_live_now or (live_state == 1)

        old_status = live_status.get(uid_str, 0)
        live_status_new[uid_str] = live_state

        # 仅直播状态从非1变成1时推送通知
        if live_state == 1 and old_status != 1:
            msg = f"@{user.get('uname', uname)} 开播了！\n[标题]{title}\n[粉丝]{user.get('follower_num', 0)}\n"
            live_messages.append(msg)
            if first_live_icon is None:
                first_live_icon = user.get("face", "")
        
        if live_state == 1:
            live_hosts.append(f"【{user.get('uname', uname)}】")

    # 保存用户和直播状态信息
    config["users"] = users
    config["live_status"] = live_status_new
    save_config(config)

    if live_messages:
        # 添加当前正在直播的主播列表到通知末尾
        if live_hosts:
            live_hosts_str = "、".join(live_hosts)
            live_messages.append(f"📽Living：{live_hosts_str}")
        message = "\n------------\n".join(live_messages)
        send_bark_notification(message, first_live_icon, bark_url, len(live_hosts))
    else:
        if any_live_now:
            live_hosts_str = "、".join(live_hosts)
            print(f"当前正在直播：{live_hosts_str}，无新增开播")
        else:
            print("当前无主播开播")

if __name__ == "__main__":
    main()