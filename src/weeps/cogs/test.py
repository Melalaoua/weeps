import discord
from discord.ext import commands

from weeps import Weeps
class Test(commands.Cog):
    def __init__(self, bot:Weeps):
        self.bot = bot
        
    @commands.command()
    async def test(self, ctx:commands.Context):
        await ctx.send("Test command works!")
        
async def setup(bot:commands.Bot):
    await bot.add_cog(Test(bot))