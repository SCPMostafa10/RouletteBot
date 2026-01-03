import discord
from discord.ext import commands
from discord.ui import Button, View
import random
import asyncio
from keep_alive import keep_alive
import os

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)

games = {}

class Player:
    def __init__(self, user, number):
        self.user = user
        self.number = number

class ShootView(View):
    def __init__(self, game_ref, shooter_player):
        super().__init__(timeout=60)
        self.game = game_ref
        self.shooter_player = shooter_player # Save the whole Player object
        self.victim = None
        self.action_taken = False
        
        # Self shoot button
        self_btn = Button(label="SHOOT SELF", style=discord.ButtonStyle.danger, custom_id="self")
        self_btn.callback = self.shoot_self
        self.add_item(self_btn)

        # Target buttons
        for p in self.game['players']:
            if p.user.id != shooter_player.user.id:
                btn = Button(label=f"Shoot #{p.number}", style=discord.ButtonStyle.primary, custom_id=str(p.number))
                btn.callback = self.make_shoot_callback(p)
                self.add_item(btn)

    def make_shoot_callback(self, target_player):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.shooter_player.user.id:
                await interaction.response.send_message("Not your turn!", ephemeral=True)
                return
            
            self.victim = target_player
            self.action_taken = True
            await interaction.response.defer()
            self.stop()
        return callback

    async def shoot_self(self, interaction: discord.Interaction):
        if interaction.user.id != self.shooter_player.user.id:
            await interaction.response.send_message("Not your turn!", ephemeral=True)
            return
        
        # Here was the fix: Set victim to the Player object, not just the user
        self.victim = self.shooter_player 
        self.action_taken = True
        await interaction.response.defer()
        self.stop()

class JoinView(View):
    def __init__(self, game_ref, channel):
        super().__init__(timeout=35) 
        self.game = game_ref
        self.channel = channel
        self.game_triggered = False
        
        for i in range(1, 17):
            btn = Button(label=str(i), style=discord.ButtonStyle.secondary, custom_id=str(i))
            btn.callback = self.make_callback(i)
            self.add_item(btn)

    async def on_timeout(self):
        if not self.game_triggered:
            await self.channel.send("❌ Game Cancelled: Not enough players joined in 35 seconds.")
            if self.channel.id in games:
                del games[self.channel.id]

    def make_callback(self, number):
        async def callback(interaction: discord.Interaction):
            user = interaction.user
            
            for p in self.game['players']:
                if p.user.id == user.id:
                    await interaction.response.send_message("You already joined!", ephemeral=True)
                    return

            self.game['players'].append(Player(user, number))
            
            for child in self.children:
                if child.custom_id == str(number):
                    child.disabled = True
                    child.style = discord.ButtonStyle.danger
                    child.label = f"{number} ({user.name})"
                    break
            
            await interaction.response.edit_message(view=self)
            
            # --- For Testing Alone: Change 3 to 1 below ---
            # --- For Real Game: Keep it 3 ---
            if len(self.game['players']) == 3 and not self.game_triggered:
                self.game_triggered = True
                self.timeout = None 
                asyncio.create_task(self.start_final_countdown(interaction))
            
        return callback

    async def start_final_countdown(self, interaction):
        await interaction.channel.send("🚨 **Minimum players reached! Game starts in 15 seconds...** (Last chance to join!)")
        
        await asyncio.sleep(15)
        
        self.stop()
        await interaction.channel.send("🔥 **Time is up! The game begins!**")
        await run_game_loop(self.channel, self.game)

async def run_game_loop(channel, game):
    while len(game['players']) > 1:
        shooter = random.choice(game['players'])
        
        embed = discord.Embed(title="🎲 Turn Phase", description=f"It is **{shooter.user.name}'s** turn (Player #{shooter.number}).\nChoose a target!", color=0xffa500)
        
        # Pass the whole Player object here
        view = ShootView(game, shooter) 
        
        msg = await channel.send(embed=embed, view=view)
        await view.wait()
        
        if not view.action_taken:
            await channel.send(f"{shooter.user.mention} took too long! Skipping turn.")
            continue

        target_player = view.victim
        
        # Safe comparison now because target_player is always a Player object
        is_self = target_player.user.id == shooter.user.id
        
        await channel.send(f"😨 {shooter.user.mention} aims at {'THEMSELVES' if is_self else target_player.user.mention}...")
        async with channel.typing():
            await asyncio.sleep(2)

        # 60% Hit chance
        hit = random.random() < 0.6
        
        if hit:
            game['players'].remove(target_player)
            death_msg = f"💥 **BANG!** {target_player.user.mention} was eliminated!"
            await channel.send(death_msg)
        else:
            await channel.send(f"☁️ **CLICK...** {target_player.user.mention} survives! The chamber was empty.")
        
        await asyncio.sleep(2)

    winner = game['players'][0]
    await channel.send(f"🏆 GAME OVER! The survivor is **{winner.user.mention}** (Player #{winner.number})!")
    if channel.id in games:
        del games[channel.id]

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')

@bot.command()
async def roulette(ctx):
    if ctx.channel.id in games:
        await ctx.send("Game already in progress here.")
        return
    
    games[ctx.channel.id] = {'players': [], 'active': False}
    
    embed = discord.Embed(title="Russian Roulette", description="Click a number to join.\n- Wait time: 35s\n- Min players: 3", color=0x00ff00)
    view = JoinView(games[ctx.channel.id], ctx.channel)
    await ctx.send(embed=embed, view=view)

# DO NOT FORGET TO PUT YOUR TOKEN HERE

keep_alive()
bot.run(os.environ.get('TOKEN'))
