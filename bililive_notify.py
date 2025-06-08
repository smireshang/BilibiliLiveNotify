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
            "room_ids": [],
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

def get_room_base_info(room_ids):
    url = "https://api.live.bilibili.com/xlive/web-room/v1/index/getRoomBaseInfo"
    params = []
    for rid in room_ids:
        params.append(("room_ids", str(rid)))
    params.append(("req_biz", "web_room_componet"))

    try:
        resp = requests.get(url, params=params, headers=HEADERS, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") == 0 and "data" in data and "by_room_ids" in data["data"]:
            return data["data"]["by_room_ids"]
        else:
            print(f"获取直播房间信息失败: {data.get('message')}")
    except Exception as e:
        print(f"请求直播房间信息异常: {e}")
    return {}

def send_bark_notification(message, icon_url, bark_url):
    if not bark_url:
        print("BARK_URL 未配置，无法推送消息")
        return
    payload = {
        "title": "【直播通知】",
        "body": message,
        "sound": "default",
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
    room_ids = config.get("room_ids", [])
    users = config.get("users", {})
    live_status = config.get("live_status", {})

    if not room_ids:
        print("配置中 room_ids 为空，退出")
        return

    # 获取直播房间信息
    room_infos = get_room_base_info(room_ids)

    live_messages = []
    first_live_icon = None
    any_live_now = False  # 标记当前是否有直播中
    live_status_new = live_status.copy()

    # 依次处理每个房间
    for rid in room_ids:
        rid_str = str(rid)
        info = room_infos.get(rid_str)
        if not info:
            # 该房间接口无返回，默认未直播
            live_status_new[rid_str] = 0
            continue

        live_state = info.get("live_status", 0)
        uid = info.get("uid")
        title = info.get("title", "")
        uname = info.get("uname", "")

        # 更新用户信息，如果用户不存在或粉丝数为0，则更新一次（避免没数据）
        user = users.get(str(uid))
        if user is None or user.get("follower_num", 0) == 0:
            user_data = update_user_info(uid)
            if user_data:
                users[str(uid)] = user_data
                user = user_data
            else:
                user = {"uname": uname, "face": "", "follower_num": 0}

        any_live_now = any_live_now or (live_state == 1)

        old_status = live_status.get(rid_str, 0)
        live_status_new[rid_str] = live_state

        # 仅直播状态从非1变成1时推送通知
        if live_state == 1 and old_status != 1:
            msg = f"{title}\n🔔{user.get('uname', uname)} 开播了！\n当前粉丝数：{user.get('follower_num', 0)}"
            live_messages.append(msg)
            if first_live_icon is None:
                first_live_icon = user.get("face", "")

    # 保存用户和直播状态信息
    config["users"] = users
    config["live_status"] = live_status_new
    save_config(config)

    if live_messages:
        message = "\n------------\n".join(live_messages)
        send_bark_notification(message, first_live_icon, bark_url)
    else:
        if any_live_now:
            print("当前无新增开播，但有主播在直播中")
        else:
            print("当前无直播开播")

if __name__ == "__main__":
    main()
