import discord
from discord import app_commands
import os

# ─── Настройки ────────────────────────────────────────────────────────────────
TOKEN = os.environ.get("SOUNDPAD_TOKEN")  # замените на токен с Discord Developer Portal
SOUNDS_DIR = "sounds"  # папка со звуковыми файлами (.mp3 / .wav / .ogg)

# ─── Инициализация ────────────────────────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True


class SoundBot(discord.Client):
    def __init__(self):
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        await self.tree.sync()
        print("✅ Slash-команды синхронизированы")


bot = SoundBot()


# ─── Утилиты ──────────────────────────────────────────────────────────────────

def get_vc(guild: discord.Guild) -> discord.VoiceClient | None:
    return discord.utils.get(bot.voice_clients, guild=guild)


def find_sound(sound_name: str) -> str | None:
    """Возвращает путь к файлу или None если не найден."""
    for ext in ("mp3", "wav", "ogg"):
        path = os.path.join(SOUNDS_DIR, f"{sound_name}.{ext}")
        if os.path.isfile(path):
            return path
    return None


def list_sounds() -> list[str]:
    """Возвращает имена файлов без расширения из папки sounds/."""
    if not os.path.isdir(SOUNDS_DIR):
        os.makedirs(SOUNDS_DIR, exist_ok=True)
        return []
    return sorted([
        os.path.splitext(f)[0]
        for f in os.listdir(SOUNDS_DIR)
        if f.lower().endswith((".mp3", ".wav", ".ogg"))
    ])


async def play_sound(voice_channel: discord.VoiceChannel, guild: discord.Guild, sound_name: str) -> str:
    """
    Подключается к каналу (если нужно) и воспроизводит звук.
    Возвращает строку с ошибкой или пустую строку если всё ок.
    """
    file_path = find_sound(sound_name)
    if not file_path:
        return f"❌ Звук **{sound_name}** не найден!"

    vc = get_vc(guild)
    if vc:
        await vc.move_to(voice_channel)
    else:
        vc = await voice_channel.connect()

    if vc.is_playing():
        vc.stop()

    source = discord.FFmpegPCMAudio(file_path)
    vc.play(source, after=lambda e: print(f"Готово: {sound_name}" + (f" | Ошибка: {e}" if e else "")))
    return ""


# ─── Кнопка воспроизведения ───────────────────────────────────────────────────

class PlayButton(discord.ui.View):
    def __init__(self, sound_name: str, requester: discord.Member):
        super().__init__(timeout=300)  # кнопка живёт 5 минут
        self.sound_name = sound_name
        self.requester = requester

    @discord.ui.button(label="▶️ Воспроизвести", style=discord.ButtonStyle.green)
    async def play_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Проверяем что нажавший находится в голосовом канале
        if not interaction.user.voice:
            await interaction.response.send_message(
                "❌ Зайди в голосовой канал чтобы воспроизвести звук!",
                ephemeral=True  # видит только нажавший
            )
            return

        error = await play_sound(interaction.user.voice.channel, interaction.guild, self.sound_name)

        if error:
            await interaction.response.send_message(error, ephemeral=True)
        else:
            await interaction.response.defer()  # молча закрываем interaction без сообщения

    @discord.ui.button(label="⏹ Стоп", style=discord.ButtonStyle.red)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        vc = get_vc(interaction.guild)
        if vc and vc.is_playing():
            vc.stop()
            await interaction.response.send_message("⏹ Остановлено", ephemeral=True)
        else:
            await interaction.response.send_message("❌ Ничего не играет", ephemeral=True)


# ─── События ──────────────────────────────────────────────────────────────────

@bot.event
async def on_ready():
    print(f"✅ Бот запущен как {bot.user} (id: {bot.user.id})")
    print(f"   Звуки ищутся в папке: ./{SOUNDS_DIR}/")


# ─── Slash-команды ────────────────────────────────────────────────────────────

@bot.tree.command(name="play", description="Показать кнопку для воспроизведения звука")
@app_commands.describe(sound="Название звука (без расширения)")
async def play(interaction: discord.Interaction, sound: str):
    """Отправляет embed с кнопкой воспроизведения."""
    file_path = find_sound(sound)

    if not file_path:
        available = list_sounds()
        hint = f"\n\n**Доступные звуки:** {', '.join(f'`{s}`' for s in available)}" if available else "\n\nПапка `sounds/` пуста."
        await interaction.response.send_message(
            f"❌ Звук **{sound}** не найден!{hint}",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title="🎵 Звук готов к воспроизведению",
        description=f"**{sound}**",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Запросил: {interaction.user.display_name}")

    view = PlayButton(sound_name=sound, requester=interaction.user)
    await interaction.response.send_message(embed=embed, view=view)


@bot.tree.command(name="sounds", description="Показать список всех доступных звуков")
async def sounds(interaction: discord.Interaction):
    available = list_sounds()
    if not available:
        await interaction.response.send_message(
            f"❌ В папке `{SOUNDS_DIR}/` нет звуковых файлов!",
            ephemeral=True
        )
        return

    listing = "\n".join(f"• `{s}`" for s in available)
    embed = discord.Embed(
        title="🎵 Доступные звуки",
        description=listing,
        color=discord.Color.blurple()
    )
    embed.set_footer(text="Используй /play <имя> для воспроизведения")
    await interaction.response.send_message(embed=embed)


@bot.tree.command(name="join", description="Зайти в твой голосовой канал")
async def join(interaction: discord.Interaction):
    if not interaction.user.voice:
        await interaction.response.send_message("❌ Ты не в голосовом канале!", ephemeral=True)
        return

    channel = interaction.user.voice.channel
    vc = get_vc(interaction.guild)

    if vc:
        await vc.move_to(channel)
    else:
        await channel.connect()

    await interaction.response.send_message(f"🔊 Зашёл в **{channel.name}**")


@bot.tree.command(name="leave", description="Выйти из голосового канала")
async def leave(interaction: discord.Interaction):
    vc = get_vc(interaction.guild)
    if not vc:
        await interaction.response.send_message("❌ Бот не в голосовом канале!", ephemeral=True)
        return

    await vc.disconnect()
    await interaction.response.send_message("👋 Вышел из канала")


@bot.tree.command(name="stop", description="Остановить воспроизведение")
async def stop(interaction: discord.Interaction):
    vc = get_vc(interaction.guild)
    if vc and vc.is_playing():
        vc.stop()
        await interaction.response.send_message("⏹ Остановлено")
    else:
        await interaction.response.send_message("❌ Ничего не играет", ephemeral=True)


# ─── Запуск ───────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(SOUNDS_DIR, exist_ok=True)
    bot.run(TOKEN)

