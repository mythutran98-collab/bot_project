import os
import json
import random
import string
import hashlib
import threading
import time
import datetime
import traceback
import discord
from discord.ext import commands
from discord.ui import View, Select, Modal, TextInput
from flask import Flask, request, jsonify

# ================== CẤU HÌNH HỆ THỐNG ==================
TOKEN = "MTQwODE3MDk5MDkzNjI2MDY4MA.G8gyDe.f-hZnNdAx1vkx-aXV9y4QzfBMKjWok-OPl7j0w"
ADMINS = [1265245644558176278, 1312771393766690836] # Discord UID của Admin
ROLE_REDEEM_ID = 1520074181620797591                 # Role ID tự động cấp khi Redeem thành công
DATA_FILE = "key.json"
SECRET_SALT = "DANG_CAP_KEY_SYSTEM_SALT_2026"       # Phải trùng khớp 100% với Script Roblox

# Khóa luồng (Lock) để tránh lỗi xung đột File dữ liệu khi Flask và Bot ghi đè cùng lúc
db_lock = threading.Lock()

# ================== QUẢN LÝ CƠ SỞ DỮ LIỆU ==================
def load_db():
    with db_lock:
        if not os.path.exists(DATA_FILE):
            return {"keys": {}}
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "keys" not in data:
                    data = {"keys": {}}
                return data
        except Exception:
            return {"keys": {}}

def save_db(db):
    with db_lock:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print("❌ Lỗi ghi File DB:", e)

# ================== FLASK API (ANTI-BYPASS ENGINE) ==================
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ Hệ thống Xác thực Key System đang hoạt động ổn định!"

@app.route('/check_key', methods=['POST'])
def check_key_api():
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
            
            # Khắc phục lỗi ép kiểu dữ liệu chuỗi/số an toàn
            if not k.get("uid") or str(k["uid"]).strip() != str(user_id).strip():
                return jsonify({"status": "fail", "msg": "Key này không thuộc về tài khoản Discord của bạn!"})

            # Xử lý gán và kiểm tra HWID thiết bị
            if k.get("hwid") is None or str(k["hwid"]).strip() == "":
                k["hwid"] = hwid
                save_db(db)
                msg = "Key hợp lệ & HWID thiết bị đã được liên kết thành công!"
            elif str(k["hwid"]).strip() == str(hwid).strip():
                msg = "Xác thực thành công!"
            else:
                return jsonify({"status": "fail", "msg": "Mã phần cứng (HWID) không khớp! Vui lòng Reset HWID trên Discord."})

            # [ANTI-BYPASS HIGH ENGINE] Tạo chữ ký Token SHA256 bảo mật chống can thiệp mạng
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

# ================== DISCORD BOT ENGINE ==================
intents = discord.Intents.default()
intents.message_content = True
intents.members = True 
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
            user_id = str(interaction.user.id).strip()

            # 1. Kiểm tra xem Key nhập vào có tồn tại hay không trước
            if key_value not in db["keys"]:
                return await interaction.response.send_message("❌ Mã Key không tồn tại trên hệ thống!", ephemeral=True)

            k = db["keys"][key_value]

            # Trường hợp: Key này đã được kích hoạt bởi chính người dùng này từ trước
            if str(k.get("uid")).strip() == user_id:
                try:
                    role = interaction.guild.get_role(ROLE_REDEEM_ID)
                    if role and role not in interaction.user.roles:
                        await interaction.user.add_roles(role)
                        return await interaction.response.send_message(f"ℹ️ Bạn đã sở hữu Key này rồi! Hệ thống đã cấp lại Role {role.mention}.", ephemeral=True)
                except Exception:
                    pass
                return await interaction.response.send_message(f"ℹ️ Bạn đã sở hữu và kích hoạt Key này (`{key_value}`) từ trước rồi!", ephemeral=True)

            # Trường hợp: Key đã bị một người KHÁC sở hữu hoàn toàn
            if k.get("uid") is not None and str(k["uid"]).strip() != "":
                return await interaction.response.send_message("❌ Key này đã được một tài khoản Discord khác sử dụng trước đó!", ephemeral=True)

            # 2. KHÓA CHẶN FIX 1 NGƯỜI SỞ HỮU 2 KEY
            # Quét toàn bộ cơ sở dữ liệu xem user hiện tại đã đứng tên bất kỳ một Key nào khác chưa
            for exist_key, exist_val in db["keys"].items():
                if exist_val.get("uid") and str(exist_val["uid"]).strip() == user_id:
                    # Chặn đứng hành động: Bảo toàn trạng thái Key cũ và không động chạm gì vào Key mới nhập vào
                    return await interaction.response.send_message(
                        f"❌ **Thao tác thất bại:** Bạn đã kích hoạt và sở hữu một key khác trước đó rồi (`{exist_key}`)! "
                        f"Mỗi tài khoản chỉ được sử dụng tối đa 1 key hệ thống. Mã bạn vừa nhập vẫn còn nguyên giá trị sử dụng.", 
                        ephemeral=True
                    )

            # 3. Tiến hành liên kết Key nếu vượt qua bộ lọc check trùng sở hữu
            k["uid"] = user_id
            k["last_reset"] = 0
            save_db(db)

            role_msg = ""
            try:
                role = interaction.guild.get_role(ROLE_REDEEM_ID)
                if role:
                    await interaction.user.add_roles(role)
                    role_msg = f"\n🎁 Bạn đã được tự động cấp role: {role.mention}!"
                else:
                    role_msg = "\n⚠️ Không tìm thấy Role cấp trên Server."
            except discord.Forbidden:
                role_msg = "\n⚠️ Bot không có quyền cấp Role! Hãy xếp Role của Bot cao hơn."
            except Exception as e:
                role_msg = f"\n⚠️ Gặp lỗi khi cấp Role: {str(e)}"

            embed = discord.Embed(
                title="✅ Kích Hoạt Thành Công!",
                description=f"🔑 Key: `{key_value}` hiện tại đã được liên kết vào tài khoản của bạn.{role_msg}",
                color=discord.Color.green()
            )
            if interaction.user.avatar:
                embed.set_thumbnail(url=interaction.user.avatar.url)
            return await interaction.response.send_message(embed=embed, ephemeral=True)

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
                return await interaction.response.send_message(f"⚠️ Thao tác thất bại: Mã Key `{key_value}` đã tồn tại trên hệ thống!", ephemeral=True)

            db["keys"][key_value] = {"uid": uid_value, "hwid": None, "last_reset": 0}
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

class DeleteKeyModal(Modal):
    def __init__(self):
        super().__init__(title="Xóa Key Hệ Thống (Admin Only)", custom_id="persistent_delete_modal")
        self.key_input = TextInput(label="Nhập chính xác mã Key cần xóa", required=True, placeholder="Nhập mã Key...")
        self.add_item(self.key_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            if interaction.user.id not in ADMINS:
                return await interaction.response.send_message("❌ Từ chối truy cập: Bạn không có quyền Admin!", ephemeral=True)

            key_value = self.key_input.value.strip()
            db = load_db()

            if key_value not in db["keys"]:
                return await interaction.response.send_message("❌ Không tìm thấy mã Key này trong hệ thống dữ liệu!", ephemeral=True)

            del db["keys"][key_value]
            save_db(db)

            embed = discord.Embed(
                title="🗑️ XÓA KEY THÀNH CÔNG!",
                description=f"✅ Mã Key `{key_value}` đã được loại bỏ hoàn toàn khỏi cơ sở dữ liệu.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        except Exception as e:
            print("❌ Lỗi DeleteKey:", e)
            await interaction.response.send_message("⚠️ Gặp lỗi khi cố gắng xóa key!", ephemeral=True)


# -------- MENU CHỌN TÙY CHỌN (SELECT MENU) --------
class MenuSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Redeem Key", emoji="🔑", description="Kích hoạt liên kết Key vào tài khoản"),
            discord.SelectOption(label="Reset HWID", emoji="♻️", description="Xóa liên kết mã thiết bị cũ (1 ngày/lần)"),
            discord.SelectOption(label="Check Key", emoji="🔍", description="Xem thông tin Key của bản thân"),
            discord.SelectOption(label="Get Script", emoji="📜", description="Lấy đoạn mã nạp Executor"),
            discord.SelectOption(label="Tạo Key (Admin)", emoji="🛠️", description="Lệnh tạo mã Key mới"),
            discord.SelectOption(label="Xóa Key (Admin)", emoji="🗑️", description="Xóa bỏ hoàn toàn mã Key khỏi hệ thống"),
            discord.SelectOption(label="Danh sách Key (Admin)", emoji="📂", description="Xuất toàn bộ cơ sở dữ liệu")
        ]
        super().__init__(placeholder="📌 Vui lòng lựa chọn tác vụ hệ thống...", options=options, custom_id="persistent_menu_select")

    async def callback(self, interaction: discord.Interaction):
        try:
            choice = self.values[0]
            user_id = str(interaction.user.id).strip()
            db = load_db()
            keys = db["keys"]

            if choice == "Redeem Key":
                return await interaction.response.send_modal(RedeemModal())

            elif choice == "Reset HWID":
                current_time = int(time.time())
                found_key = False
                for k, v in keys.items():
                    if v.get("uid") and str(v["uid"]).strip() == user_id:
                        found_key = True
                        last_reset = v.get("last_reset", 0)
                        
                        # GIỚI HẠN 24 GIỜ (86400 giây)
                        time_passed = current_time - last_reset
                        if time_passed < 86400:
                            time_left = 86400 - time_passed
                            readable_time = str(datetime.timedelta(seconds=time_left)).split(".")[0]
                            return await interaction.response.send_message(f"❌ Bạn đã Reset HWID trước đó rồi. Vui lòng đợi thêm `{readable_time}` để thực hiện lại tác vụ này!", ephemeral=True)
                        
                        v["hwid"] = None
                        v["last_reset"] = current_time
                        save_db(db)
                        embed = discord.Embed(
                            title="♻️ Reset HWID Hoàn Tất",
                            description=f"✅ Mã khóa phần cứng cũ của Key `{k}` đã được gỡ bỏ. Bạn có thể mở game trên thiết bị mới ngay bây giờ!",
                            color=discord.Color.orange()
                        )
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                if not found_key:
                    await interaction.response.send_message("❌ Lỗi: Bạn chưa sở hữu hay kích hoạt bất kỳ mã Key nào để có thể thực hiện!", ephemeral=True)

            elif choice == "Check Key":
                found_key = False
                for k, v in keys.items():
                    if v.get("uid") and str(v["uid"]).strip() == user_id:
                        found_key = True
                        embed = discord.Embed(
                            title="🔍 Dữ Liệu Tra Cứu Key",
                            description=f"🔑 **Key:** `{k}`\n💻 **HWID Khóa Máy:** `{v.get('hwid') or 'Chưa khóa thiết bị nào'}`",
                            color=discord.Color.purple()
                        )
                        return await interaction.response.send_message(embed=embed, ephemeral=True)
                if not found_key:
                    await interaction.response.send_message("❌ Hệ thống không tìm thấy dữ liệu Key gắn với tài khoản của bạn!", ephemeral=True)

            elif choice == "Get Script":
                found_key = False
                for k, v in keys.items():
                    if v.get("uid") and str(v["uid"]).strip() == user_id:
                        found_key = True
                        # Đã sửa lại cú pháp gán biến chuỗi script chuẩn hóa, loại bỏ lỗi thụt dòng lề
                        script_code = f'_G.Key = "{k}"\n_G.DiscordID = "{user_id}"\nloadstring(game:HttpGet("raw.githubusercontent.com/mythutran98-collab/bot_project/refs/heads/main/VND.txt"))()'
                        try:
                            await interaction.user.send(f"🤖 **Đoạn mã chạy script dành riêng cho bạn:**\n```lua\n{script_code}\n```")
                            return await interaction.response.send_message("📩 Script đã gửi riêng vào tin nhắn riêng (DM) của bạn!", ephemeral=True)
                        except discord.Forbidden:
                            return await interaction.response.send_message("❌ Không thể gửi DM! Hãy mở cài đặt bảo mật cho phép nhận tin nhắn từ thành viên cùng server.", ephemeral=True)
                if not found_key:
                    await interaction.response.send_message("❌ Bạn không thể lấy script khi chưa kích hoạt (Redeem) Key!", ephemeral=True)

            elif choice == "Tạo Key (Admin)":
                if interaction.user.id not in ADMINS:
                    return await interaction.response.send_message("❌ Bạn không có quyền quản trị để thực hiện!", ephemeral=True)
                return await interaction.response.send_modal(CreateKeyModal())

            elif choice == "Xóa Key (Admin)":
                if interaction.user.id not in ADMINS:
                    return await interaction.response.send_message("❌ Bạn không có quyền quản trị để thực hiện!", ephemeral=True)
                return await interaction.response.send_modal(DeleteKeyModal())

            elif choice == "Danh sách Key (Admin)":
                if interaction.user.id not in ADMINS:
                    return await interaction.response.send_message("❌ Bạn không có quyền quản trị để thực hiện!", ephemeral=True)

                if not keys:
                    return await interaction.response.send_message("⚠️ Cơ sở dữ liệu đang rỗng, không có key nào!", ephemeral=True)

                msg = "📂 **DANH SÁCH TOÀN BỘ KEY HỆ THỐNG:**\n"
                for k, v in keys.items():
                    uid_display = v.get('uid') if v.get('uid') else 'Chưa gán'
                    hwid_display = v.get('hwid') if v.get('hwid') else 'Trống'
                    msg += f"• Key: `{k}` | UID: `{uid_display}` | HWID: `{hwid_display}`\n"

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
    if not TOKEN or TOKEN == "":
        print("❌ LỖI NGHIÊM TRỌNG: Biến TOKEN đang trống!")
    else:
        threading.Thread(target=run_flask, daemon=True).start()
        bot.run(TOKEN)
