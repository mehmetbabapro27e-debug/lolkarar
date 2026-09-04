import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import math
import random

import discord
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class MyBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("Komutlar senkronize edildi!")

bot = MyBot()

PAGE_SIZE = 25  # Discord bir select menüde en fazla 25 seçenek gösterebiliyor


def normalize_str(text: str) -> str:
    """Türkçe karakterleri ve büyük/küçük harfleri standart formata getirir."""
    if not text:
        return ""
    replacements = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})
    return text.translate(replacements).lower()


# ------------------- ARAMA MODALI -------------------
class SearchModal(Modal, title="Oyuncu Ara"):
    arama = TextInput(
        label="İsim ara",
        placeholder="Örn: alpha",
        required=False,
        max_length=50,
    )

    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__()
        self.parent_view = parent_view

    async def on_submit(self, interaction: discord.Interaction):
        query = normalize_str(self.arama.value.strip())
        self.parent_view.search_query = self.arama.value.strip()

        if query:
            def matches(member: discord.Member) -> bool:
                display_name = normalize_str(member.display_name)
                username = normalize_str(member.name)
                global_name = normalize_str(member.global_name) if member.global_name else ""
                return query in display_name or query in username or query in global_name

            self.parent_view.filtered_members = [
                m for m in self.parent_view.all_members if matches(m)
            ]
        else:
            self.parent_view.filtered_members = self.parent_view.all_members

        self.parent_view.current_page = 0
        self.parent_view.rebuild()
        await interaction.response.edit_message(
            content=self.parent_view.build_content(),
            view=self.parent_view,
        )


# ------------------- OYUNCU SEÇME MENÜSÜ (SAYFALI) -------------------
class PlayerSelect(Select):
    def __init__(self, parent_view: "TeamBuilderView"):
        page_members = parent_view.get_page_members()

        options = []
        for member in page_members:
            options.append(discord.SelectOption(
                label=member.display_name[:100],
                description=f"@{member.name}"[:100],
                value=str(member.id),
                default=str(member.id) in parent_view.selected_ids,
            ))

        if not options:
            options = [discord.SelectOption(label="Bu aramayla eşleşen oyuncu bulunamadı", value="none")]

        super().__init__(
            placeholder=f"Oyuncu seç... (Sayfa {parent_view.current_page + 1}/{parent_view.total_pages()})",
            min_values=0,
            max_values=len(options) if options[0].value != "none" else 1,
            options=options,
            disabled=options[0].value == "none"
        )
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        page_ids = {opt.value for opt in self.options if opt.value != "none"}
        self.parent_view.selected_ids -= page_ids
        for val in self.values:
            if val != "none":
                self.parent_view.selected_ids.add(val)

        self.parent_view.rebuild()
        await interaction.response.edit_message(
            content=self.parent_view.build_content(),
            view=self.parent_view,
        )


# ------------------- ARAMA / SAYFALAMA / ONAY BUTONLARI -------------------
class SearchButton(Button):
    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__(label="🔍 Ara", style=discord.ButtonStyle.secondary, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal(self.parent_view))


class ClearSearchButton(Button):
    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__(label="✖️ Aramayı Temizle", style=discord.ButtonStyle.secondary, row=1)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        self.parent_view.search_query = ""
        self.parent_view.filtered_members = self.parent_view.all_members
        self.parent_view.current_page = 0
        self.parent_view.rebuild()
        await interaction.response.edit_message(
            content=self.parent_view.build_content(),
            view=self.parent_view,
        )


class PrevPageButton(Button):
    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__(label="⬅️ Önceki Sayfa", style=discord.ButtonStyle.primary, row=2)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.current_page > 0:
            self.parent_view.current_page -= 1
        self.parent_view.rebuild()
        await interaction.response.edit_message(
            content=self.parent_view.build_content(),
            view=self.parent_view,
        )


class NextPageButton(Button):
    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__(label="Sonraki Sayfa ➡️", style=discord.ButtonStyle.primary, row=2)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        if self.parent_view.current_page < self.parent_view.total_pages() - 1:
            self.parent_view.current_page += 1
        self.parent_view.rebuild()
        await interaction.response.edit_message(
            content=self.parent_view.build_content(),
            view=self.parent_view,
        )


class ConfirmButton(Button):
    def __init__(self, parent_view: "TeamBuilderView"):
        super().__init__(label="✅ Takım Oluştur!", style=discord.ButtonStyle.green, row=3)
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        view = self.parent_view
        secilen_idler = list(view.selected_ids)

        secilen_isimler = []
        for uid in secilen_idler:
            member = view.guild.get_member(int(uid))
            if member:
                secilen_isimler.append(member.display_name)
            else:
                secilen_isimler.append(uid)

        if not secilen_isimler:
            await interaction.response.send_message("❌ Hiç oyuncu seçmedin!", ephemeral=True)
            return
        if len(secilen_isimler) != view.kisi_sayisi:
            await interaction.response.send_message(
                f"❌ {view.kisi_sayisi} kişi seçmelisin! Sen {len(secilen_isimler)} kişi seçtin.",
                ephemeral=True,
            )
            return

        rastgele_liste = secilen_isimler.copy()
        random.shuffle(rastgele_liste)
        yari = len(rastgele_liste) // 2
        takim1 = rastgele_liste[:yari]
        takim2 = rastgele_liste[yari:]

        embed = discord.Embed(title=f"🎮 {view.secilen_mod} Takımlar Oluştu!", color=discord.Color.blue())
        embed.add_field(name="🟦 Takım 1", value="\n".join(takim1) if takim1 else "Boş", inline=True)
        embed.add_field(name="🟥 Takım 2", value="\n".join(takim2) if takim2 else "Boş", inline=True)
        embed.set_footer(text="İyi oyunlar! 🎯")

        await interaction.response.edit_message(content="", embed=embed, view=None)


# ------------------- ANA SAYFALI SEÇİM VIEW'İ -------------------
class TeamBuilderView(View):
    def __init__(self, kisi_sayisi, mod_adi, guild):
        super().__init__(timeout=None)
        self.kisi_sayisi = kisi_sayisi
        self.secilen_mod = mod_adi
        self.guild = guild

        self.all_members = [m for m in guild.members if not m.bot]
        self.filtered_members = self.all_members
        self.search_query = ""
        self.current_page = 0
        self.selected_ids = set()

        self.rebuild()

    def total_pages(self):
        return max(1, math.ceil(len(self.filtered_members) / PAGE_SIZE))

    def get_page_members(self):
        start = self.current_page * PAGE_SIZE
        end = start + PAGE_SIZE
        return self.filtered_members[start:end]

    def build_content(self):
        arama_bilgisi = f" | 🔍 Arama: **{self.search_query}**" if self.search_query else ""
        return (
            f"**{self.secilen_mod}** seçtin. Lütfen tam **{self.kisi_sayisi}** oyuncu seç ve "
            f"'Takım Oluştur' butonuna bas.\n"
            f"Sayfa **{self.current_page + 1}/{self.total_pages()}** | "
            f"Seçili: **{len(self.selected_ids)}/{self.kisi_sayisi}**{arama_bilgisi}"
        )

    def rebuild(self):
        # Sayfa numarasını sınırların dışına çıkmayacak şekilde ayarla
        max_page = self.total_pages() - 1
        if self.current_page > max_page:
            self.current_page = max_page

        self.clear_items()
        self.add_item(PlayerSelect(self))
        self.add_item(SearchButton(self))
        if self.search_query:
            self.add_item(ClearSearchButton(self))
        if self.total_pages() > 1:
            self.add_item(PrevPageButton(self))
            self.add_item(NextPageButton(self))
        self.add_item(ConfirmButton(self))


# ------------------- MOD SEÇME MENÜSÜ -------------------
class ModSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="1v1", description="1 kişiye karşı 1 kişi", emoji="⚔️"),
            discord.SelectOption(label="2v2", description="2 kişiye karşı 2 kişi", emoji="⚔️"),
            discord.SelectOption(label="3v3", description="3 kişiye karşı 3 kişi", emoji="⚔️"),
            discord.SelectOption(label="4v4", description="4 kişiye karşı 4 kişi", emoji="⚔️"),
            discord.SelectOption(label="5v5", description="5 kişiye karşı 5 kişi", emoji="⚔️"),
        ]
        super().__init__(placeholder="Mod seç...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        secilen_mod = self.values[0]
        kisi_sayisi = int(secilen_mod[0]) * 2

        view = TeamBuilderView(kisi_sayisi, secilen_mod, interaction.guild)

        await interaction.response.edit_message(
            content=view.build_content(),
            view=view,
        )


# ------------------- ANA KOMUT /belirle -------------------
@bot.tree.command(name="belirle", description="LOL takım oluşturma aracı")
async def belirle(interaction: discord.Interaction):
    view = View(timeout=None)
    view.add_item(ModSelect())
    await interaction.response.send_message("**🏆 Hangi modda oynanacak?** Aşağıdan seç.", view=view, ephemeral=False)


# ------------------- RENDER WEB SUNUCUSU -------------------
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'Bot is running!')

def run_web():
    server = HTTPServer(('0.0.0.0', 10000), Handler)
    server.serve_forever()

threading.Thread(target=run_web, daemon=True).start()

# ------------------- BOTU ÇALIŞTIR -------------------
bot.run(os.getenv("BOT_TOKEN"))
