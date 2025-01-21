import discord
from discord.ext import commands

from meeps import Meeps

from emanations.cache import clear_cache

class AdminDiscord(commands.Cog):
    def __init__(self, bot:Meeps):
        self.bot = bot
        

    @commands.command()
    @commands.is_owner()
    async def updatetree(self, ctx:commands.Context) -> None:
        """Update change in app_commands, do not use as a routine under risk of timeout by discord"""
        guild = discord.Object(ctx.guild.id)
        # We'll copy in the global commands to test with:
        self.bot.tree.copy_global_to(guild=guild)
        # followed by syncing to the testing guild.
        await self.bot.tree.sync(guild=guild)

        await ctx.message.add_reaction("👍")

    @commands.command()
    @commands.is_owner()
    async def clear_cache(self, ctx:commands.Context) -> None:
        """Clear the cache"""
        
        await ctx.message.add_reaction("👍")


async def setup(bot:Meeps):
    clear_cache()
    await bot.add_cog(AdminDiscord(bot))