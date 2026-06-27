import os
import json
import random
import string
import hashlib
import threading
import traceback
import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
from flask import Flask, request, jsonify

# ================== CẤU HÌNH HỆ THỐNG ==================
TOKEN = os.environ.get("MTQwODE3MDk5MDkzNjI2MDY4MA.G8gyDe.f-hZnNdAx1vkx-aXV9y4QzfBMKjWok-OPl7j0w")
ADMINS = [1265245644558176278, 1312771393766690836] # Discord UID của Admin
ROLE_REDEEM_ID = 1520074181620797591                 # Role ID tự động cấp khi Redeem thành công
DATA_FILE = "key.json"
SECRET_SALT = "DANG_CAP_KEY_SYSTEM_SALT_2026"       # Phải trùng khớp 100% với Script Roblox

# ================== FLASK API (ANTI-BYPASS ENGINE) ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Hệ thống Xác thực Key System đang hoạt động ổn định!"

@app.route('/check_key', methods=['POST'])
def check_key():
    try:
        data = request.json
        if not data:
            return jsonify({"status": "fail", "msg": "Dữ liệu trống!"})

        key = data.get("key", "").strip()
        user_id = data.get("id", "").strip()
        hwid = data.get("hwid", "").strip()

        if not key or not user_id or not hwid:
            return jsonify({"status": "fail", "msg": "Thiếu thông tin tham số gửi lên!"})

        db = load_db()
        if key in db["keys"]:
            k = db["keys"][key]
            
            # Kiểm tra xem Key có thuộc về User ID Discord này không (Đã Redeem chưa)
            if str(k["uid"]) != str(user_id):
                return jsonify({"status": "fail", "msg": "Key này không thuộc về tài khoản Discord của bạn!"})

            # Xử lý gán và kiểm tra HWID thiết bị
            if k["hwid"] is None or k["hwid"] == "":
                k["hwid"] = hwid
                save_db(db)
                msg = "Key hợp lệ & HWID thiết bị đã được liên kết thành công!"
            elif str(k["hwid"]) == str(hwid):
                msg = "Xác thực thành công!"
            else:
                return jsonify({"status": "fail", "msg": "Mã phần cứng (HWID) không trùng khớp! Vui lòng Reset HWID trên Discord."})

            # [ANTI-BYPASS HIGH ENGINE] Tạo chữ ký Token SHA256 bảo mật chống can thiệp mạng chặn gói tin
            raw_string = f"{key}{user_id}{hwid}{SECRET_SALT}"
            server_token = hashlib.sha256(raw_string.encode('utf-8')).hexdigest()

            return jsonify({
                "status": "success", 
                "msg": msg,
                "token": server_token
            })
            
        return jsonify({"status": "fail", "msg": "Key không tồn tại hoặc đã hết hạn!"})
    except Exception as e:
        print("❌ Lỗi API Flask:", e)
        return jsonify({"status": "fail", "msg": "Lỗi xử lý nội bộ tại Server!"})

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# ================== QUẢN LÝ CƠ SỞ DỮ LIỆU ==================
def load_db():
    if not os.path.exists(DATA_FILE):
        return {"keys": {}}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"keys": {}}

def save_db(db):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, indent=4, ensure_ascii=False)

# ================== DISCORD BOT ENGINE ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True # BẮT BUỘC BẬT TÍNH NĂNG NÀY TRÊN DEVELOPER PORTAL ĐỂ CẤP ĐƯỢC ROLE
bot = commands.Bot(command_prefix=",", intents=intents)

# -------- CÁC LỚP MODAL TƯƠNG TÁC --------
class RedeemModal(Modal):
    def __init__(self):
        super().__init__(title="Kích hoạt (Redeem) Key", custom_id="persistent_redeem_modal")
        self.key_input = TextInput(label="Nhập mã Key của bạn", style=discord.TextStyle.short, placeholder="Ví dụ: AbC123XyZ...", custom_id="input_redeem_key")
        self.add_item(self.key_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            db = load_db()
            key_value = self.key_input.value.strip()

            if key_value in db["keys"]:
                k = db["keys"][key_value]

                # Trường hợp 1: Key chưa ai sử dụng -> Tiến hành kích hoạt
                if k["uid"] is None or k["uid"] == "":
                    k["uid"] = str(interaction.user.id)
                    save_db(db)

                    # Tiến hành tự động trao Role cho người dùng
                    role_msg = ""
                    try:
                        role = interaction.guild.get_role(ROLE_REDEEM_ID)
                        if role:
                            await interaction.user.add_roles(role)
                            role_msg = f"\n🎁 Bạn đã được tự động cấp role: {role.mention}!"
                        else:
                            role_msg = "\n⚠️ Không tìm thấy Role cấp trên Server. Vui lòng báo Admin kiểm tra ID Role."
                    except discord.Forbidden:
                        role_msg = "\n⚠️ Bot không có quyền cấp Role! Hãy kéo Role của Bot lên cao hơn Role cần cấp."
                    except Exception as e:
                        role_msg = f"\n⚠️ Gặp lỗi khi cấp Role: {str(e)}"

                    embed = discord.Embed(
                        title="✅ Kích Hoạt Thành Công!",
                        description=f"🔑 Key: `{key_value}` hiện tại đã được liên kết vào tài khoản Discord của bạn.{role_msg}",
                        color=discord.Color.green()
                    )
                    if interaction.user.avatar:
                        embed.set_thumbnail(url=interaction.user.avatar.url)
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

                # Trường hợp 2: Key đã kích hoạt bởi chính user đó
                elif str(k["uid"]) == str(interaction.user.id):
                    # Đề phòng user đã kích hoạt nhưng bị mất role (ví dụ: out server vào lại), cấp lại role luôn
                    try:
                        role = interaction.guild.get_role(ROLE_REDEEM_ID)
                        if role and role not in interaction.user.roles:
                            await interaction.user.add_roles(role)
                            return await interaction.response.send_message(f"ℹ️ Bạn đã sở hữu Key này rồi! Hệ thống đã cấp lại Role {role.mention} cho bạn.", ephemeral=True)
                    except Exception:
                        pass
                    return await interaction.response.send_message("ℹ️ Bạn đã sở hữu và kích hoạt Key này từ trước rồi!", ephemeral=True)
                
                # Trường hợp 3: Key bị trùng với người khác
                else:
                    return await interaction.response.send_message("❌ Key này đã được người khác sử dụng trước đó!", ephemeral=True)
            else:
                await interaction.response.send_message("❌ Mã Key không tồn tại hệ thống hoặc không chính xác!", ephemeral=True)
        except Exception as e:
            print("❌ Lỗi Redeem:", e)
            await interaction.response.send_message("⚠️ Có lỗi xảy ra trong quá trình kích hoạt mã!", ephemeral=True)

class CreateKeyModal(Modal):
    def __init__(self):
        super().__init__(title="Tạo Key Mới (Admin Only)", custom_id="persistent_create_modal")
        self.key_input = TextInput(label="Nhập Key mong muốn (để trống để Random)", required=False, custom_id="input_create_key", placeholder="Để trống nếu muốn tự tạo ngẫu nhiên...")
        self.uid_input = TextInput(label="Gán sẵn Discord UID (để trống tự liên kết)", required=False, custom_id="input_create_uid", placeholder="Nhập ID người nhận nếu có...")
        self.add_item(self.key_input)
        self.add_item(self.uid_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id not in ADMINS:
                return await interaction.response.send_message("❌ Từ chối truy cập: Bạn không có quyền Admin!", ephemeral=True)

            key_value = self.key_input.value.strip() if self.key_input.value else None
            if not key_value:
                key_value = ''.join(random.choices(string.ascii_letters + string.digits, k=16))

            uid_value = self.uid_input.value.strip() if self.uid_input.value else None
            if uid_value == "":
                uid_value = None

            db = load_db()
            if key_value in db["keys"]:
                return await interaction.response.send_message("⚠️ Mã Key này đã trùng lặp và tồn tại trên cơ sở dữ liệu!", ephemeral=True)

            db["keys"][key_value] = {"uid": uid_value, "hwid": None}
            save_db(db)

            embed = discord.Embed(
                title="🎉 TẠO KEY THÀNH CÔNG!",
                description=f"🔑 **Mã Key:**\n```{key_value}```",
                color=discord.Color.blue()
            )
            embed.add_field(name="👤 Sở hữu UID", value=f"`{uid_value}`" if uid_value else "`Tự do (Chưa gán)`", inline=True)
            embed.add_field(name="💻 Trạng thái HWID", value="`Chưa khóa máy`", inline=True)
            if interaction.user.avatar:
                embed.set_footer(text=f"Khởi tạo bởi {interaction.user}", icon_url=interaction.user.avatar.url)

            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            print("❌ Lỗi CreateKey:", e)
            await interaction.response.send_message("⚠️ Gặp lỗi bất ngờ khi hệ thống tạo key!", ephemeral=True)

# -------- MENU CHỌN TÙY CHỌN (SELECT MENU) --------
class MenuSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Redeem Key", emoji="🔑", description="Kích hoạt liên kết Key vào tài khoản"),
            discord.SelectOption(label="Reset HWID", emoji="♻️", description="Xóa liên kết mã thiết bị cũ"),
            discord.SelectOption(label="Check Key", emoji="🔍", description="Xem thông tin Key của bản thân"),
            discord.SelectOption(label="Get Script", emoji="📜", description="Lấy đoạn mã nạp Executor"),
            discord.SelectOption(label="Tạo Key (Admin)", emoji="🛠️", description="Lệnh tạo mã Key mới"),
            discord.SelectOption(label="Danh sách Key (Admin)", emoji="📂", description="Xuất toàn bộ cơ sở dữ liệu")
        ]
        super().__init__(placeholder="📌 Vui lòng lựa chọn tác vụ hệ thống...", options=options, custom_id="persistent_menu_select")

    async def callback(self, interaction: discord.Interaction):
        try:
            choice = self.values[0]
            user_id = str(interaction.user.id)
            db = load_db()
            keys = db["keys"]

            if choice == "Redeem Key":
                return await interaction.response.send_modal(RedeemModal())

            elif choice == "Reset HWID":
                for k, v in keys.items():
                    if str(v["uid"]) == user_id:
                        v["hwid"] = None
                        save_db(db)
                        embed = discord.Embed(
                            title="♻️ Reset HWID Hoàn Tất",
                            description=f"✅ Mã khóa phần cứng cũ của Key `{k}` đã được gỡ bỏ thành công. Bây giờ bạn có thể mở game trên thiết bị mới!",
                            color=discord.Color.orange()
                        )
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                await interaction.response.send_message("❌ Lỗi: Bạn chưa sở hữu hay kích hoạt bất kỳ mã Key nào để Reset!", ephemeral=True)

            elif choice == "Check Key":
                for k, v in keys.items():
                    if str(v["uid"]) == user_id:
                        embed = discord.Embed(
                            title="🔍 Dữ Liệu Tra Cứu Key",
                            description=f"🔑 **Key:** `{k}`\n💻 **HWID Khóa Máy:** `{v['hwid'] or 'Chưa khóa thiết bị nào'}`",
                            color=discord.Color.purple()
                        )
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                await interaction.response.send_message("❌ Hệ thống tìm kiếm không thấy dữ liệu Key của bạn!", ephemeral=True)

            elif choice == "Get Script":
                for k, v in keys.items():
                    if str(v["uid"]) == user_id:
                        script = f'```lua\ngetgenv().Key = "{k}"\ngetgenv().ID = "{user_id}"\nloadstring(game:HttpGet("[https://raw.githubusercontent.com/mythutran98-collab/bot_project/main/VND.txt](https://raw.githubusercontent.com/mythutran98-collab/bot_project/main/VND.txt)"))()\n```'
                        try:
                            await interaction.user.send(f"🤖 **Đoạn mã chạy script dành riêng cho bạn:**\n{script}")
                            return await interaction.response.send_message("📩 Script đã gửi riêng vào tin nhắn riêng (DM) của bạn!", ephemeral=True)
                        except Exception:
                            return await interaction.response.send_message("❌ Không thể gửi tin nhắn riêng cho bạn! Hãy mở khóa tính năng nhận tin nhắn từ người lạ ở cài đặt bảo mật Discord.", ephemeral=True)
                await interaction.response.send_message("❌ Bạn không thể lấy script khi chưa kích hoạt kích hoạt (Redeem) Key!", ephemeral=True)

            elif choice == "Tạo Key (Admin)":
                if interaction.user.id not in ADMINS:
                    return await interaction.response.send_message("❌ Bạn không có quyền quản trị cấp cao để thực hiện!", ephemeral=True)
                return await interaction.response.send_modal(CreateKeyModal())

            elif choice == "Danh sách Key (Admin)":
                if interaction.user.id not in ADMINS:
                    return await interaction.response.send_message("❌ Bạn không có quyền quản trị cấp cao để thực hiện!", ephemeral=True)

                if not keys:
                    return await interaction.response.send_message("⚠️ Hệ thống hiện đang rỗng dữ liệu, chưa có key nào được tạo!", ephemeral=True)

                msg = "📂 **DANH SÁCH TOÀN BỘ KEY HỆ THỐNG:**\n"
                for k, v in keys.items():
                    msg += f"• Key: `{k}` | UID: `{v['uid']}` | HWID: `{v['hwid']}`\n"

                if len(msg) > 1900:
                    with open("keys_list.txt", "w", encoding="utf-8") as f:
                        f.write(msg)
                    await interaction.response.send_message(
                        "📂 Danh sách vượt quá ký tự, đã xuất thành File văn bản đính kèm:",
                        file=discord.File("keys_list.txt"),
                        ephemeral=True
                    )
                else:
                    embed = discord.Embed(title="📂 Quản Lý Cơ Sở Dữ Liệu Key", description=msg, color=discord.Color.teal())
                    await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            print("❌ Lỗi Xử Lý Thanh Menu Tác Vụ:", e)
            traceback.print_exc()
            await interaction.response.send_message("⚠️ Có lỗi hệ thống phát sinh trong khi xử lý hành động của bạn!", ephemeral=True)

class MenuView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(MenuSelect())

# -------- CÁC SỰ KIỆN & LỆNH ĐIỀU KHIỂN --------
@bot.event
async def on_ready():
    print(f"🤖 Đăng nhập thành công bot: {bot.user.name}")
    bot.add_view(MenuView())

@bot.command()
async def menu(ctx):
    embed = discord.Embed(
        title="📌 HỆ THỐNG QUẢN LÝ KEY HUB CHUYÊN NGHIỆP",
        description="Chào mừng bạn đến với bảng điều khiển VND HUB.\nVui lòng mở thanh danh sách thả xuống dưới đây để chọn thao tác mong muốn.",
        color=discord.Color.gold()
    )
    if ctx.author.avatar:
        embed.set_thumbnail(url=ctx.author.avatar.url)
    embed.set_footer(text="Bản quyền vận hành phát triển bởi VND HUB V2 © 2026")

    await ctx.send(embed=embed, view=MenuView())

# ================== KHỞI CHẠY KHÔNG GIAN ĐA LUỒNG ==================
if __name__ == "__main__":
    if not TOKEN or "DÁN_TOKEN" in TOKEN:
        print("❌ LỖI NGHIÊM TRỌNG: Biến TOKEN đang trống hoặc chưa được thay thế chuỗi chuẩn!")
    else:
        threading.Thread(target=run_flask, daemon=True).start()
        bot.run(TOKEN)
