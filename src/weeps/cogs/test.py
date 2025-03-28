import discord
from discord.ext import commands

from weeps import Weeps
from weeps_utils.config import Prompts
from emanations.utils import split_into_shorter_messages


class Test(commands.Cog):
    def __init__(self, bot:Weeps):
        self.bot = bot
    
    def remove_think_tags(self, text):
        """
        Remove all content between <think> and </think> tags, including the tags themselves.
        
        Args:
            text (str): Input text containing potentially multiple <think> sections
        
        Returns:
            str: Text with all <think> sections removed
        """
        import re
        
        # Regex pattern to match <think> tags and everything between them
        # The re.DOTALL flag allows . to match newline characters
        pattern = r'<think>.*?</think>'
        
        # Replace all matches with an empty string
        cleaned_text = re.sub(pattern, '', text, flags=re.DOTALL)
        
        return cleaned_text.strip()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        async with guild.system_channel.typing():
            response = await self.bot.llm(
                messages=[
                    {"role" : "system", "content":Prompts.persona,},
                    {"role":"user", "content":f"Tu viens de rejoindre le serveur {guild.name}. Fais tes salutations de manière brève et en restant en accord avec ton personnage. Message:"}]
            )
            text = self.remove_think_tags(response.content)
            
            for msg in split_into_shorter_messages(text):
                await guild.system_channel.send(msg)

async def setup(bot:commands.Bot):
    await bot.add_cog(Test(bot))