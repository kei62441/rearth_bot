import json
import re
import math
import asyncio
import urllib.request
import discord
from discord.ext import tasks

# ===== 設定 =====
DISCORD_TOKEN = "ここにBotトークン"
CHANNEL_ID = 123456789012345678      # 通知チャンネルID
MENTION_ROLE_ID = 987654321098765432 # CollapseAlert ロールID

JSON_URL = "https://map.rearth.xyz/war/tiles/_markers_/marker_world.json"
CHECK_INTERVAL = 60  # 秒
RADIUS = 1000  # ブロック


# ===== 共通処理 =====

def polygon_area(xs, zs):
    area = 0
    n = len(xs)
    for i in range(n):
        j = (i + 1) % n
        area += xs[i] * zs[j] - xs[j] * zs[i]
    return abs(area) / 2


def fetch_json():
    req = urllib.request.Request(
        JSON_URL,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read().decode("utf-8"))


def load_all_nations():
    data = fetch_json()
    areas = data["sets"]["towny.markerset"]["areas"]

    nations = {}

    for v in areas.values():
        name = v.get("label")
        xs = v.get("x", [])
        zs = v.get("z", [])
        desc = v.get("desc", "")

        cx = sum(xs) / len(xs) if xs else 0
        cz = sum(zs) / len(zs) if zs else 0
        area = polygon_area(xs, zs) if len(xs) >= 3 else 0
        collapsed = "崩壊" in desc

        if name not in nations:
            nations[name] = {
                "area": 0,
                "cx": 0,
                "cz": 0,
                "count": 0,
                "collapsed": False
            }

        nations[name]["area"] += area
        nations[name]["cx"] += cx
        nations[name]["cz"] += cz
        nations[name]["count"] += 1
        if collapsed:
            nations[name]["collapsed"] = True

    for n in nations.values():
        n["cx"] = n["cx"] / n["count"]
        n["cz"] = n["cz"] / n["count"]

    return nations


def nearby_nations(target, nations):
    result = []
    tx, tz = target["cx"], target["cz"]

    for name, info in nations.items():
        if info is target:
            continue
        d = math.hypot(tx - info["cx"], tz - info["cz"])
        if d <= RADIUS:
            result.append(name)

    return result


def map_url(x, z):
    return f"https://map.rearth.xyz/war/#world;flat;{int(x)},64,{int(z)};0"


# ===== Discord Bot =====

intents = discord.Intents.default()
client = discord.Client(intents=intents)

known_collapsed = set()


@tasks.loop(seconds=CHECK_INTERVAL)
async def check_collapses():
    global known_collapsed

    channel = client.get_channel(CHANNEL_ID)
    if channel is None:
        return

    nations = load_all_nations()
    current = {name for name, n in nations.items() if n["collapsed"]}

    new_collapses = current - known_collapsed
    known_collapsed = current

    role_mention = f"<@&{MENTION_ROLE_ID}>"

    for name in new_collapses:
        n = nations[name]
        nearby = nearby_nations(n, nations)

        msg = (
            f"{role_mention}\n"
            f"🚨 **新たな崩壊国家を検出** 🚨\n\n"
            f"🟥 国名: **{name}**\n"
            f"📍 中心座標: ({int(n['cx'])}, {int(n['cz'])})\n"
            f"🧱 国土面積: {int(n['area'])}\n"
            f"🧭 半径{RADIUS}以内の国:\n"
            f"{', '.join(nearby) if nearby else 'なし'}\n\n"
            f"🗺️ マップURL:\n{map_url(n['cx'], n['cz'])}"
        )

        await channel.send(msg)


@client.event
async def on_ready():
    print(f"ログイン完了: {client.user}")
    check_collapses.start()


client.run(DISCORD_TOKEN)
