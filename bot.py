import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import discord
from discord import app_commands
from discord.ui import Select, View, Button, Modal, TextInput
import random

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
        
        # Oyuncu seçme menüsünü göster
        view = View(timeout=None)
        # Arama butonu
        arama_butonu = Button(label="🔍 İsim Ara", style=discord.ButtonStyle.primary)
        view.add_item(arama_butonu)
        
        # Sunucudaki tüm üyeleri al (botlar hariç)
        uyeler = [m for m in interaction.guild.members if not m.bot]
        
        # Sayfalama için PlayerSelectView'i oluştur
        player_view = PlayerSelectView(uyeler, kisi_sayisi, secilen_mod, 0)
        view.add_item(player_view)
        
        # Butona tıklanınca arama modal'ı aç
        async def arama_callback(interaction_buton: discord.Interaction):
            modal = SearchModal(uyeler, kisi_sayisi, secilen_mod)
            await interaction_buton.response.send_modal(modal)
        
        arama_butonu.callback = arama_callback
        
        await interaction.response.edit_message(
            content=f"**{secilen_mod}** seçtin. Aşağıdan oyuncuları seç veya 🔍 İsim Ara butonuna tıkla.",
            view=view
        )

# ------------------- OYUNCU SEÇME (Sayfalar ile) -------------------
class PlayerSelectView(Select):
    def __init__(self, uyeler, kisi_sayisi, mod_adi, sayfa):
        self.uyeler = uyeler
        self.kisi_sayisi = kisi_sayisi
        self.mod_adi = mod_adi
        self.sayfa = sayfa
        self.sayfa_boyutu = 15  # Her sayfada 15 kişi
        
        # Sayfadaki üyeleri al
        baslangic = sayfa * self.sayfa_boyutu
        bitis = baslangic + self.sayfa_boyutu
        sayfadaki_uyeler = uyeler[baslangic:bitis]
        
        options = []
        for member in sayfadaki_uyeler:
            options.append(discord.SelectOption(
                label=member.display_name[:50],
                value=str(member.id)
            ))
        
        super().__init__(
            placeholder=f"Sayfa {sayfa+1}/{(len(uyeler)-1)//self.sayfa_boyutu + 1} - {len(sayfadaki_uyeler)} kişi",
            min_values=1,
            max_values=kisi_sayisi,
            options=options
        )
    
    async def callback(self, interaction: discord.Interaction):
        # Seçilenleri saklamak için view'e ekle
        self.view.secilenler = self.values
        await interaction.response.defer()

# ------------------- ARAMA MODAL'ı -------------------
class SearchModal(Modal, title="🔍 Oyuncu Ara"):
    def __init__(self, uyeler, kisi_sayisi, mod_adi):
        super().__init__()
        self.uyeler = uyeler
        self.kisi_sayisi = kisi_sayisi
        self.mod_adi = mod_adi
        
        self.arama_kutusu = TextInput(
            label="İsim yazmaya başla",
            placeholder="Örn: Leac, Ahmet, ...",
            required=True,
            max_length=50
        )
        self.add_item(self.arama_kutusu)
    
    async def on_submit(self, interaction: discord.Interaction):
        arama = self.arama_kutusu.value.lower()
        
        # Arama yap
        eslesenler = []
        for member in self.uyeler:
            if arama in member.display_name.lower() or arama in member.name.lower():
                eslesenler.append(member)
        
        if not eslesenler:
            await interaction.response.send_message(f"❌ '{self.arama_kutusu.value}' ile eşleşen üye bulunamadı.", ephemeral=True)
            return
        
        # Sonuçları göster
        view = View(timeout=None)
        # Sonuçları Select menüsüne koy
        options = []
        for member in eslesenler[:25]:  # Discord limiti
            options.append(discord.SelectOption(
                label=member.display_name[:50],
                value=str(member.id)
            ))
        
        secim = Select(
            placeholder=f"Bulunan {len(eslesenler)} kişiden seç ({self.kisi_sayisi} kişi)",
            min_values=1,
            max_values=self.kisi_sayisi,
            options=options
        )
        
        # Seçilenleri sakla
        secilenler = []
        
        async def secim_callback(interaction_sel: discord.Interaction):
            nonlocal secilenler
            secilenler = secim.values
            await interaction_sel.response.defer()
        
        secim.callback = secim_callback
        
        onay_butonu = Button(label="✅ Takım Oluştur!", style=discord.ButtonStyle.green)
        
        async def buton_callback(interaction_buton: discord.Interaction):
            if not secilenler:
                await interaction_buton.response.send_message("❌ Hiç oyuncu seçmedin!", ephemeral=True)
                return
            if len(secilenler) != self.kisi_sayisi:
                await interaction_buton.response.send_message(f"❌ {self.kisi_sayisi} kişi seçmelisin! Sen {len(secilenler)} kişi seçtin.", ephemeral=True)
                return
            
            # İsimlere çevir
            secilen_isimler = []
            for uid in secilenler:
                member = interaction.guild.get_member(int(uid))
                if member:
                    secilen_isimler.append(member.display_name)
            
            # Takımları oluştur
            rastgele_liste = secilen_isimler.copy()
            random.shuffle(rastgele_liste)
            yari = len(rastgele_liste) // 2
            takim1 = rastgele_liste[:yari]
            takim2 = rastgele_liste[yari:]
            
            embed = discord.Embed(title=f"🎮 {self.mod_adi} Takımlar Oluştu!", color=discord.Color.blue())
            embed.add_field(name="🟦 Takım 1", value="\n".join(takim1) if takim1 else "Boş", inline=True)
            embed.add_field(name="🟥 Takım 2", value="\n".join(takim2) if takim2 else "Boş", inline=True)
            embed.set_footer(text="İyi oyunlar! 🎯")
            
            await interaction_buton.response.edit_message(content="", embed=embed, view=None)
        
        onay_butonu.callback = buton_callback
        
        view.add_item(secim)
        view.add_item(onay_butonu)
        
        await interaction.response.send_message(
            content=f"🔍 '{self.arama_kutusu.value}' için {len(eslesenler)} sonuç bulundu. Lütfen **{self.kisi_sayisi}** kişi seç.",
            view=view,
            ephemeral=False
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
