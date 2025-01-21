import discord
from discord.ext import commands

import datetime
from sqlalchemy import asc, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from meeps import Meeps
from emanations.database import AsyncDb
from emanations.database.crud import CrudFactory
from emanations.database.models.discordmodels import (
    DiscordGuild, DiscordGuildSchema, DiscordGuildUpdateSchema,
    DiscordChannel, DiscordChannelSchema, DiscordChannelUpdateSchema,
    DiscordUser, DiscordUserSchema, DiscordUserUpdateSchema,
    DiscordMessage, DiscordMessageSchema, DiscordMessageUpdateSchema, DiscordUserUpdateJoinedAtScema,
    DiscordPrivateMessage, DiscordPrivateMessageSchema,
    DiscordMention, DiscordMentionSchema
)


class MessageDiscord(commands.Cog):
    def __init__(self, bot:Meeps):
        self.bot = bot
        self.db = self.bot.db
        self.llm = self.bot.llm
        self.stability = self.bot.stability
        self.elevenlabs = self.bot.elevenlabs
        self.nomen = self.bot.nomen

    @commands.Cog.listener()
    async def on_message(
        self, 
        message:discord.Message
    ) -> None:
        """When a message is sent in the discord, load message in database"""        
        if isinstance(message.channel, (discord.DMChannel, discord.GroupChannel)):     
            message_create = DiscordPrivateMessageSchema(
                uuid = message.id,
                author_uuid = message.author.id,
                created_at = message.created_at.replace(tzinfo=None),
                content = message.content,
                metadatas = await message_metadata(message)
            )
            return await load_privates_messages(message)

        
        ### GUILDS
        guild_create = DiscordGuildSchema(
            uuid = message.guild.id,
            created_at = message.guild.created_at.replace(tzinfo=None),
            name = message.guild.name
        )
        GuildCrud = CrudFactory(DiscordGuild)
        await GuildCrud.bulk_upserts(self.db, [guild_create], index_elements = ['uuid'])
        
        ### CHANNELS
        channel_create = DiscordChannelSchema(
            uuid = message.channel.id,
            created_at = message.channel.created_at.replace(tzinfo=None),
            name = message.channel.name,
            type = str(message.channel.type),
            guild_uuid = message.channel.guild.id,
            metadatas = await channel_metadatas(message.channel)
        )
        ChannelCrud = CrudFactory(DiscordChannel)
        await ChannelCrud.bulk_upserts(self.db, [channel_create], index_elements = ['uuid'])

        ### USERS
        user_create = DiscordUserSchema(
            uuid = message.author.id,
            created_at = message.author.created_at.replace(tzinfo=None),
            guild_uuid = message.guild.id,
            pseudo = message.author.name,
            is_bot = message.author.bot,
            is_active=True,
            joined_at = message.author.joined_at.replace(tzinfo=None),
        )
        UserCrud = CrudFactory(DiscordUser)
        await UserCrud.bulk_upserts(self.db, [user_create], index_elements = ['uuid', 'guild_uuid'], exclude_columns=['created_at', 'joined_at', 'ang_account_uuid'])
        
        ### MESSAGES
        message_create = DiscordMessageSchema(
            uuid = message.id,
            created_at = message.created_at.replace(tzinfo=None),
            guild_uuid = message.guild.id,
            channel_uuid = message.channel.id,
            author_uuid = message.author.id,
            content = message.content,
            reference_uuid = message.reference.message_id if message.reference else None,
            metadatas = await message_metadata(message)
        )
        MessageCrud = CrudFactory(DiscordMessage)
        await MessageCrud.bulk_upserts(self.db, [message_create], index_elements = ['uuid'])

        ### MENTIONS
        mentions = []
        for user in message.mentions:
            mentions.append(DiscordMentionSchema(
                message_uuid = message.id,
                user_uuid = message.author.id,
                mention_uuid = user.id,
                guild_uuid = message.guild.id
            ))
        if mentions : await load_mentions(self.db, mentions)

    @commands.command()
    @commands.is_owner()
    async def update_join_date(
        self, 
        ctx : commands.Context
    ) -> None:
        """Update users's join date creation by fetching their oldest message in the database"""
        
        DiscordUserCrud = CrudFactory(DiscordUser)
        users = await DiscordUserCrud.get_all(self.db) 
        
        async with self.db.session() as session:
            for user in users:
                user : DiscordUser = user
                q = select(DiscordMessage).filter_by(author_uuid=user.uuid).order_by(asc(DiscordMessage.created_at))
                results = await session.execute(q)
                first_message = results.unique().scalars().first()

                user_update = DiscordUserUpdateJoinedAtScema(
                    joined_at = first_message.created_at
                )
                await DiscordUserCrud.update_by_id(self.db, user_update, nested_ids=[user.uuid, user.guild_uuid], columns=['uuid', 'guild_uuid'])

        await ctx.message.add_reaction("✅")


class MessageDiscordSweep(commands.Cog):
    """This class is responsible for storing guilds, messages and channels inside the database upon sweep commands. Theses command are not meant to be used often, they are one time command to store all the messages inside the database. This process can take a very long time for big servers.
    """
    def __init__(self, bot:Meeps):
        self.bot = bot
        self.db = self.bot.db 

        self.count = 0
        self.messages_chunk = 1000
        
        self.channels_tags = []
        self.channels_create = []
        self.channels_update = []
        

        self.users_tags = []
        self.users_create = []
        self.users_update = []
        
        self.messages_create = []
        self.messages_update = []

        self.mentions_create = []

        self.ChannelCrud = CrudFactory(DiscordChannel)
        self.UserCrud = CrudFactory(DiscordUser)
        self.MessageCrud = CrudFactory(DiscordMessage)
        

    async def flush(self) -> None:
        """Flush all data inside the database
        """
        self.count = 0  


        if self.channels_create:
            await self.ChannelCrud.bulk_upserts(self.db, self.channels_create, index_elements = ['uuid'])
            self.channels_tags = []
            self.channels_create = []
            self.channels_update = []

        if self.users_create:
            await self.UserCrud.bulk_upserts(self.db, self.users_create, index_elements = ['uuid', 'guild_uuid'])
            self.users_tags = []
            self.users_create = []
            self.users_update = []

        if self.messages_create:
            await self.MessageCrud.bulk_upserts(self.db, self.messages_create, index_elements = ['uuid'])
            self.messages_create = []
            self.messages_update = []

        if self.mentions_create :
            await load_mentions(self.db, self.mentions_create)
            self.mentions_create = []


    @commands.command()
    @commands.is_owner()
    async def sweep(
        self, 
        ctx:commands.Context
    ) -> None:
        """Guild Owner's command to store all server's message inside the database, this process can take a very long time for big servers.
        
        Args:
            ctx (commands.Context): Discord context
        
        Returns:
            None
        """
        await ctx.send("Je commence le sweep")
        
        for channel in ctx.guild.threads:
            await self.handle_channel(channel)

        for forum in ctx.guild.forums:
            for channel in forum.threads:
                await self.handle_channel(channel)

        for channel in ctx.guild.text_channels:
            await self.handle_channel(channel)
        
        if self.count > 0 : await self.flush()
        await ctx.send("Sweep done")


    async def handle_channel(
        self,
        channel : discord.TextChannel | discord.Thread
    ) -> None :
        """Handle message to store in database
        
        Args: 
            channel (discord.TextChannel | discord.Thread): Discord Channel

        Returns:
            None
        """
        if not channel.id in self.channels_tags:    
            self.channels_create.append(DiscordChannelSchema(
                        uuid = channel.id,
                        created_at = channel.created_at.replace(tzinfo=None),
                        name = channel.name,
                        type = str(channel.type),
                        guild_uuid = channel.guild.id,
                        metadatas = await channel_metadatas(channel)
                    )
                )
            self.channels_update.append(DiscordChannelUpdateSchema(
                    name = channel.name,
                    updated_at = datetime.datetime.now().replace(tzinfo=None)
                )
            )
            self.channels_tags.append(channel.id)

        async for message in channel.history(limit = None):
            message : discord.Message = message
            if not message.author.id in self.users_tags:
                user_create = DiscordUserSchema(
                    uuid = message.author.id,
                    created_at = message.author.created_at.replace(tzinfo=None),
                    guild_uuid = message.guild.id,
                    pseudo = message.author.name,
                    is_bot = message.author.bot,
                    is_active=True,
                    joined_at = message.author.joined_at.replace(tzinfo=None) if hasattr(message.author, 'joined_at') else message.author.created_at.replace(tzinfo=None)
                    )
                self.users_create.append(user_create)
                user_update = DiscordUserUpdateSchema(
                    pseudo=message.author.name,
                    updated_at = datetime.datetime.now().replace(tzinfo=None)
                )
                self.users_update.append(user_update)
                
                self.users_tags.append(message.author.id)


            self.messages_create.append(DiscordMessageSchema(
                uuid = message.id,
                created_at = message.created_at.replace(tzinfo=None),
                guild_uuid = message.guild.id,
                channel_uuid = message.channel.id,
                author_uuid = message.author.id,
                content = message.content,
                reference_uuid = message.reference.message_id if message.reference else None,
                metadatas = await message_metadata(message)
            ))
            self.messages_update.append(DiscordMessageUpdateSchema(
                content = message.content,
                updated_at = datetime.datetime.now().replace(tzinfo=None)
            ))

            for mention in message.mentions:
                self.mentions_create.append(DiscordMentionSchema(
                    message_uuid = message.id,
                    user_uuid = message.author.id,
                    mention_uuid = mention.id,
                    guild_uuid = message.guild.id
                ))
            
            self.count += 1
            if self.count >= self.messages_chunk:
                await self.flush()

async def setup(bot:Meeps) -> None:
    await bot.add_cog(MessageDiscord(bot))
    await bot.add_cog(MessageDiscordSweep(bot))


async def load_privates_messages(
        session:AsyncSession,
        messages_create : list[DiscordPrivateMessageSchema]
) -> None:
    """Builk create private message in database
    
    Args:
        message (list[DiscordPrivateMessageSchema]): List of private messages schema from emanations package 

    Returns:
        None
    """
    PrivateMessageCrud = CrudFactory(DiscordPrivateMessage)
    message = await PrivateMessageCrud.create_many(session, messages_create)
    if not message:
        raise Exception("Error while creating private message") 


async def message_metadata(
        message:discord.Message
) -> dict:
    """Return additional information to str like activity, interaction, stickers.
    
    Args:
        message (discord.Message): Discord message
    
    Returns:
        str: Additional information
    """
    metadata = {}
    if getattr(message, 'attachments', None):
        metadata["attachments"] = []
        for attachment in message.attachments:
            attachment : discord.Attachment = attachment
            attachment_dict = {}
            attachment_dict["filename"] = attachment.filename
            attachment_dict['url'] = attachment.url
            attachment_dict['proxy_url'] = attachment.proxy_url
            attachment_dict['size'] = attachment.size
            attachment_dict['ephemeral'] = attachment.ephemeral
            attachment_dict["voice_message"] = attachment.is_voice_message()
            attachment_dict['duration'] = attachment.duration
            attachment_dict['waveform'] = attachment.waveform
            attachment_dict['spoiler'] = attachment.is_spoiler()
            metadata["attachments"].append(attachment_dict)

    metadata["channel_mentions"] = [channel.name for channel in message.channel_mentions]    
    metadata["mention_everyone"] = message.mention_everyone
    metadata["roles_mentions"] = [role.name for role in message.role_mentions]
    metadata["flags"] = {k : v for k,v in iter(message.flags)}
    
    if getattr(message, "interaction_metadata"):
        metadata["interaction_metadata"] = {
            "type" : message.interaction_metadata.type,
            "original_response_message_id" : message.interaction_metadata.original_response_message_id,
            "interacted_message_id" : message.interaction_metadata.interacted_message_id,

        }
    
    metadata["stickers"] = [sticker.name for sticker in message.stickers]
    
    metadata["embeds"] = []
    for embed in message.embeds:
        metadata["embeds"].append(embed.to_dict())    
    return metadata


async def channel_metadatas(
    channel : discord.TextChannel | discord.Thread
) -> dict:
    """Return channel's metadatas.
    
    Args:
        channel (discord.TextChannel | discord.Thread): Discord channel

    Returns:
        dict: Channel's metadatas
    """
    metadatas = {}
    metadatas["nsfw"] = channel.is_nsfw()
    metadatas["news"] = channel.is_news()
    
    if isinstance(channel, discord.Thread):
        metadatas['archived'] = channel.archived
        metadatas['flags'] = {k : v for k,v in iter(channel.flags)}
        metadatas['message_count'] = channel.message_count
        metadatas['parent'] = channel.parent.id
        metadatas['starter_message'] = channel.id
        
    return metadatas


async def load_mentions(
        db:AsyncDb,
        mentions_create : list[DiscordMentionSchema]
) -> None:
    """Bulk upserts mentions in database. If mention already exists, update it.
    
    Args:
        mentions_create (list[DiscordMentionSchema]) : list of mention schema from emanations package
        mentions_update (list[DiscordMentionUpdateSchema]) : list of mention update schema from emanations package to dictate which columns to update, take the colums of the first update schema in the list.
    
    Returns:
        None
    """
    async with db.session() as session:
        insert_stmt = insert(DiscordMention).values([data.model_dump() for data in mentions_create]).on_conflict_do_nothing(index_elements=['uuid', 'message_uuid', 'user_uuid', 'mention_uuid'])
        await session.execute(insert_stmt)
        await session.commit()
