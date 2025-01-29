import os
from dotenv import load_dotenv
load_dotenv()

import discord
from discord.ext import commands

import asyncio
import logging
import logging.handlers

logger = logging.getLogger('discord')
logger.setLevel(logging.INFO)

handler = logging.handlers.RotatingFileHandler(
filename='weeps-discord.log',
encoding='utf-8',
maxBytes=32 * 1024 * 1024,  # 32 MiB
backupCount=5,  # Rotate through 5 files
)
dt_fmt = '%Y-%m-%d %H:%M:%S'
formatter = logging.Formatter('[{asctime}] [{levelname:<8}] {name}: {message}', dt_fmt, style='{')
handler.setFormatter(formatter)
logger.addHandler(handler)


from emanations import DiscordBot

from emanations.database import AsyncDb
from emanations.api.llm import LLMFactory
from emanations.api.diffusion.stability import StabilityAI
from emanations.api.tts.elevenlabs import ElevenLabs

from weeps_utils.config import Emojis
class Weeps(DiscordBot):
    def __init__(
        self, 
        *args,
        **kwargs
    ) -> commands.Bot:
        """Initialize Weeps bot"""
        super().__init__(*args, **kwargs)

    @property
    def emojis(self):
        return Emojis

    
async def main():
    db = AsyncDb(os.getenv("DB_URI"))
    llm = LLMFactory("anthropic", os.getenv("ANTHROPIC_KEY"))
    stability = StabilityAI(os.getenv("STABILITY_KEY"))
    elevenlabs = ElevenLabs(os.getenv("ELEVENLABS_KEY"))

    await db.begin()
    async with Weeps(
        name="Weeps",
        db = db,
        cogs_path="cogs",
        llm = llm,
        stability = stability,
        elevenlabs = elevenlabs,
        
        intents=discord.Intents.all(),
        command_prefix= list(os.getenv('PREFIXES')),
        strip_after_prefix = True,
        help_command=None,
    ) as bot:
        try:
            await bot.start(os.getenv("DISCORD_TOKEN"))
        except KeyboardInterrupt:
            await bot.close()

if __name__ == '__main__':
    asyncio.run(main())