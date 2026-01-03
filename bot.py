import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import asyncio
import os

# =====================
# Global Game Storage
# =====================
games = {}

# =====================
# Game Classes
# =====================
class Player:
    def __init__(self, user, number):
        self.user = user
        self.number = number


class ShootView(View):
    def __init__(self, game, shooter):
        super().__init__(timeout=60)
        self.game = game
        self.shooter = shooter
        self.victim = None
        self.action_taken = False

        self_btn = Button(label="أطلق على نفسي 💀", style=discord.ButtonStyle.danger)
        self_btn.callback = self.shoot_self
        self.add_item(self_btn)

        for p in self.game["players"]:
            if p.user.id != shooter.user.id:
                btn = Button(label=f"ضرب #{p.number}", style=discord.ButtonStyle.primary)
                btn.callback = self.make_callback(p)
                self.add_item(btn)

    def make_callback(self, target):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.shooter.user.id:
                await interaction.response.send_message(
                    "✋ ليس دورك.", ephemeral=True
                )
                return

            self.victim = target
            self.action_taken = True
            await interaction.response.defer()
            self.stop()

        return callback

    async def shoot_self(self, interaction: discord.Interaction):
        if interaction.user.id != self.shooter.user.id:
            await interaction.response.send_message(
                "✋ ليس دورك.", ephemeral=True
            )
            return

        self.victim = self.shooter
        self.action_taken = True
        await interaction.response.defer()
        self.stop()


class JoinView(View):
    def __init__(self, game, channel, message):
        super().__init__(timeout=None)
        self.game = game
        self.channel = channel
        self.message = message
        self.started = False

        for i in range(1, 17):
            btn = Button(label=str(i), style=discord.ButtonStyle.secondary)
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    def make_callback(self, number):
        async def callback(interaction: discord.Interaction):
            if any(p.user.id == interaction.user.id for p in self.game["players"]):
                await interaction.response.send_message(
                    "⚠️ أنت مسجل بالفعل.", ephemeral=True
                )
                return

            self.game["players"].append(Player(interaction.user, number))

            for child in self.children:
                if child.label == str(number):
                    child.disabled = True
                    child.label = f"{number} ({interaction.user.name})"
                    child.style = discord.ButtonStyle.danger

            await interaction.response.edit_message(view=self)

            if len(self.game["players"]) >= 3 and not self.started:
                self.started = True
                asyncio.create_task(self.start_game())

        return callback

    async def start_game(self):
        await asyncio.sleep(10)
        await self.message.edit(view=None)
        await run_game(self.channel, self.game)


# =====================
# Game Loop
# =====================
async def run_game(channel, game):
    while len(game["players"]) > 1:
        shooter = random.choice(game["players"])
        embed = discord.Embed(
            title="🎲 الدور على",
            description=f"{shooter.user.mention} (#{shooter.number})",
            color=0xffa500,
        )

        view = ShootView(game, shooter)
        msg = await channel.send(embed=embed, view=view)
        await view.wait()

        if not view.action_taken:
            await channel.send("⌛ تم تفويت الدور.")
            continue

        target = view.victim
        await asyncio.sleep(2)

        if random.random() < 0.6:
            game["players"].remove(target)
            await channel.send(f"💥 {target.user.mention} خرج من اللعبة!")
        else:
            await channel.send(f"😅 نجى {target.user.mention}!")

        await asyncio.sleep(2)

    winner = game["players"][0]
    await channel.send(f"🏆 الفائز: {winner.user.mention}")
    games.pop(channel.id, None)


# =====================
# Bot Setup
# =====================
intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")


@bot.command()
async def roulette(ctx):
    if ctx.channel.id in games:
        await ctx.send("⚠️ هناك لعبة بالفعل.")
        return

    games[ctx.channel.id] = {"players": []}

    embed = discord.Embed(
        title="🔫 الروليت الروسية",
        description="اختر رقمك للانضمام (الحد الأدنى 3 لاعبين)",
        color=0x00ff00,
    )

    msg = await ctx.send(embed=embed)
    view = JoinView(games[ctx.channel.id], ctx.channel, msg)
    await msg.edit(view=view)


# =====================
# Run Bot
# =====================
TOKEN = os.environ.get("TOKEN")
if not TOKEN:
    raise RuntimeError("TOKEN environment variable not set")

bot.run(TOKEN)
