import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
import json
import os
import random
import string
import traceback
from flask import Flask, request, jsonify
import threading

# ================== CẤU HÌNH ==================
TOKEN = "YOUR_DISCORD_BOT_TOKEN"  # Thay token bot của bạn
ADMINS = [1265245644558176278,
          1312771393766690836]     # Thay bằng Discord UID của bạn
DATA_FILE = "keys.json"

# ================== FLASK API (keep_alive) ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Bot đang chạy!"

@app.route('/check_key', methods=['POST'])
def check_key():
    data = request.json
    key = data.get("key")
    hwid = data.get("hwid")

    db = load_db()
    if key in db["keys"]:
        k = db["keys"][key]
        if k["hwid"] is None:
            k["hwid"] = hwid
            save_db(db)
            return jsonify({"status": "success", "msg": "Key hợp lệ & HWID đã bind"})
        elif k["hwid"] == hwid:
            return jsonify({"status": "success", "msg": "Key hợp lệ"})
        else:
            return jsonify({"status": "fail", "msg": "HWID không khớp"})
    return jsonify({"status": "fail", "msg": "Key không tồn tại"})

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ================== QUẢN LÝ DATA ==================
def load_db():
    if not os.path.exists(DATA_FILE):
        return {"keys": {}}
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_db(db):
    with open(DATA_FILE, "w") as f:
        json.dump(db, f, indent=4)

# ================== DISCORD BOT ==================
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix=",", intents=intents)

# -------- MODALS --------
class RedeemModal(Modal, title="Redeem Key"):
    key = TextInput(label="Nhập Key", style=discord.TextStyle.short)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            db = load_db()
            key_value = self.key.value.strip()

            if key_value in db["keys"]:
                k = db["keys"][key_value]

                # Nếu key chưa gán user nào thì cho redeem
                if k["uid"] is None:
                    k["uid"] = str(interaction.user.id)
                    save_db(db)

                    embed = discord.Embed(
                        title="✅ Redeem Key Thành Công!",
                        description=f"🔑 Key: `{key_value}` đã được gán cho bạn.",
                        color=discord.Color.green()
                    )
                    embed.set_thumbnail(url=interaction.user.avatar.url if interaction.user.avatar else None)
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                # Nếu key đã gán cho chính user này thì cho phép check lại
                elif k["uid"] == str(interaction.user.id):
                    return await interaction.response.send_message("✅ Bạn đã redeem key này rồi!", ephemeral=True)

                # Nếu key đã gán cho người khác thì từ chối
                else:
                    return await interaction.response.send_message("❌ Key này đã được sử dụng bởi người khác!", ephemeral=True)

            else:
                await interaction.response.send_message("❌ Key không hợp lệ!", ephemeral=True)

        except Exception as e:
            print("❌ Lỗi Redeem:", e)
            await interaction.response.send_message("⚠️ Lỗi redeem key!", ephemeral=True)

class CreateKeyModal(Modal, title="Tạo Key"):
    key = TextInput(label="Nhập Key (để trống sẽ random)", required=False)
    uid = TextInput(label="UID (Discord ID hoặc để trống)", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id not in ADMINS:
                return await interaction.response.send_message("❌ Bạn không có quyền!", ephemeral=True)

            key_value = self.key.value.strip() if self.key.value else None
            if not key_value:
                key_value = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

            uid_value = self.uid.value.strip() if self.uid.value else None
            if uid_value == "":
                uid_value = None

            db = load_db()
            if key_value in db["keys"]:
                return await interaction.response.send_message("⚠️ Key này đã tồn tại!", ephemeral=True)

            db["keys"][key_value] = {"uid": uid_value, "hwid": None}
            save_db(db)

            embed = discord.Embed(
                title="🎉 TẠO KEY THÀNH CÔNG!",
                description=f"🔑 Key mới:\n```{key_value}```",
                color=discord.Color.blue()
            )
            embed.add_field(name="👤 UID", value=f"`{uid_value}`" if uid_value else "`Chưa gán`", inline=True)
            embed.add_field(name="💻 HWID", value="`Chưa gán`", inline=True)
            embed.set_footer(
                text=f"Tạo bởi {interacti
