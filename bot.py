import os
import discord
from discord import app_commands
from discord.ui import Select, View, Button
import random

# 🔴 KENDİ OYUNCU LİSTENİ BURAYA YAZ (İstediğin kadar değiştir)
OYUNCU_LISTESI = [
    "Ahmet", "Mehmet", "Ayşe", "Fatma", "Ali",
    "Veli", "Selim", "Can", "Eda", "Leyla",
    "Mert", "Deniz", "Zeynep", "Efe", "Berra"
]

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

        view = View()
        player_select = PlayerSelect(kisi_sayisi, secilen_mod)
        view.add_item(player_select)

        onay_butonu = Button(label="✅ Takım Oluştur!", style=discord.ButtonStyle.green)
        view.add_item(onay_butonu)

        view.kisi_sayisi = kisi_sayisi
        view.secilen_mod = secilen_mod
        view.oyuncu_listesi = OYUNCU_LISTESI

        async def buton_callback(interaction_buton: discord.Interaction):
            secilenler = player_select.values
            if not secilenler:
                await interaction_buton.response.send_message("❌ Hiç oyuncu seçmedin!", ephemeral=True)
                return
            if len(secilenler) != view.kisi_sayisi:
                await interaction_buton.response.send_message(f"❌ {view.kisi_sayisi} kişi seçmelisin! Sen {len(secilenler)} kişi seçtin.", ephemeral=True)
                return

            rastgele_liste = secilenler.copy()
            random.shuffle(rastgele_liste)
            yari = len(rastgele_liste) // 2
            takim1 = rastgele_liste[:yari]
            takim2 = rastgele_liste[yari:]

            embed = discord.Embed(title=f"🎮 {view.secilen_mod} Takımlar Oluştu!", color=discord.Color.blue())
            embed.add_field(name="🟦 Takım 1", value="\n".join(takim1) if takim1 else "Boş", inline=True)
            embed.add_field(name="🟥 Takım 2", value="\n".join(takim2) if takim2 else "Boş", inline=True)
            embed.set_footer(text="İyi oyunlar! 🎯")

            await interaction_buton.response.edit_message(content="", embed=embed, view=None)

        onay_butonu.callback = buton_callback

        await interaction.response.edit_message(
            content=f"**{secilen_mod}** seçtin. Lütfen tam **{kisi_sayisi}** oyuncu seç ve 'Takım Oluştur' butonuna bas.",
            view=view
        )

# ------------------- OYUNCU SEÇME MENÜSÜ -------------------
class PlayerSelect(Select):
    def __init__(self, kisi_sayisi, mod_adi):
        options = []
        for isim in OYUNCU_LISTESI:
            options.append(discord.SelectOption(label=isim, value=isim))
        super().__init__(
            placeholder=f"{kisi_sayisi} oyuncu seç...",
            min_values=1,
            max_values=kisi_sayisi,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer()

# ------------------- ANA KOMUT /belirle -------------------
@bot.tree.command(name="belirle", description="LOL takım oluşturma aracı")
async def belirle(interaction: discord.Interaction):
    view = View()
    view.add_item(ModSelect())
    await interaction.response.send_message("**🏆 Hangi modda oynanacak?** Aşağıdan seç.", view=view, ephemeral=False)

# ------------------- BOTU ÇALIŞTIR -------------------
bot.run(os.getenv("BOT_TOKEN"))
