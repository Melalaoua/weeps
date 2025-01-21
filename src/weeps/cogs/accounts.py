
import discord
from discord.ext import commands

from meeps import Meeps

from emanations.database.models.angelarium import AngAccount
from emanations.discord import get_ang_account_from_discord, get_bank_account_from_discord, get_discord_user, create_ang_account_from_discord, swift_from_discord


class AngAccountDiscord(commands.Cog):
    def __init__(
            self,
            bot:Meeps,
    ):
        """AngAccount Discord Cog for creating, displaying Ang Account datas"""
        self.bot = bot
        self.db = self.bot.db
        self.llm = self.bot.llm
    
    async def delete_message(
            self, 
            ctx:commands.Context, 
            delete_after:int=5
        ) -> None:
        """Delete the message of the context"""
        try:
            await ctx.message.delete(delay=delete_after)
        except: pass


    @commands.hybrid_command(
            description="Compte Angelarium (classe, expérience, stats, ...). Si aucun membre n'est spécifié, affiche ton compte Angelarium. Sinon, affiche le compte angelarium du membre spécifié.",
            usage="icompte [@member (optionnel)]")
    async def compte(
        self, 
        ctx:commands.Context,
        member:discord.Member = None
    ):
        if member is None : member = ctx.author
        
        ang_account = await get_ang_account_from_discord(self.db, member=member)
        if not ang_account:
            if member.id == ctx.author.id : 
                view = AngAccountCreationView(self.bot, member)
                await ctx.send(view.message, view=view)
            else:
                await ctx.send(f"Pas de compte {member.guild.name}.", delete_after=5)
        else:
            view = AngAccountView(self.bot, member, ang_account)
            await view.send(ctx)

        await self.delete_message(ctx)


    @commands.hybrid_command(
        description="Informations AngBank (soniums, transactions, ...). Si aucun membre n'est spécifié, affiche ton compte. Sinon, affiche le compte AngBank du membre spécifié.",
    )
    async def bank(
        self,
        ctx:commands.Context,
        member:discord.Member = None
    ):
        if member is None: member = ctx.author

        ang_bank = await get_bank_account_from_discord(self.db, member=member)
        
        await ctx.send(f"Ang Bank : {ang_bank}")
        await self.delete_message(ctx)


    @commands.hybrid_command(
            description="Affiche l'avatar de l'auteur du message ou du membre spécifié",
            usage="iavatar [member (optionnel)]"
    )
    async def avatar(
        self, 
        ctx:commands.Context, 
        member:discord.Member=None
    ) -> None:
        try:
            await ctx.message.delete()
        except: pass
        await ctx.send(member.avatar if member else ctx.author.avatar)


    @commands.hybrid_command(
            description="Affiche les informations discord de l'auteur du message ou du membre spécifié",
            usage="icard [@member (optionnel)]"
    )
    async def card(
        self,
        ctx:commands.Context,
        member:discord.Member=None 
    ) -> None :
        member = member if member else ctx.author

        user = await get_discord_user(self.db, member)
        if user:
            embed = discord.Embed(
                title=member.name,
                description=f"- A rejoint le serveur le {user.joined_at.strftime('%d/%m/%Y à %Hh%m')}\n- A rejoint l'application discord le {user.created_at.strftime('%d/%m/%Y')}"
            )
            embed.set_thumbnail(url=member.avatar).set_footer(icon_url=ctx.guild.icon, text=ctx.guild.name)
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Pas de données pour {member.name}")

async def setup(bot:Meeps) -> None:
    await bot.add_cog(AngAccountDiscord(bot))



## VIEWS

class AngAccountCreationView(discord.ui.View):
    def __init__(
            self,
            bot: Meeps,
            member:discord.Member,
    ):
        """AngAccountCreationView for creating an Ang Account
        
        Args:
            bot (Meeps): Meeps bot instance
            member (discord.Member): Discord member instance
        
        returns:
            Discord.ui.View : Discord view instance
        """
        super().__init__()
        self.bot = bot
        self.db = self.bot.db        
        self.llm = self.bot.llm

        self.member = member
        self.message = f"Pas de compte {self.member.guild.name}. Veux-tu en créer un ?"


    @discord.ui.button(label="Oui", style=discord.ButtonStyle.success)
    async def confirm(self, interaction:discord.Interaction, button:discord.ui.Button):
        ang_account : AngAccount = await create_ang_account_from_discord(self.db, self.member)
        await interaction.response.send_message(f"Compte {self.member.guild.name} créé ! Refait icompte pour afficher tes infos.")
        
        await interaction.message.delete()
        self.stop()


    @discord.ui.button(label="Non", style=discord.ButtonStyle.danger)
    async def refuse(self, interaction:discord.Interaction, button:discord.ui.Button):
        await interaction.message.delete()
        self.stop()


class AngAccountView(discord.ui.View):
    def __init__(
            self,
            bot: Meeps,
            member:discord.Member,
            ang_account:AngAccount,
    ):
        """AngAccountView for displaying an Ang Account
        
        Args:
            bot (Meeps): Meeps bot instance
            member (discord.Member): Discord member instance
            ang_account (AngAccount): Ang Account instance
        
        returns:
            Discord.ui.View : Discord view instance
        """
        super().__init__()
        self.bot = bot
        self.db = self.bot.db
        self.llm = self.bot.llm

        self.member = member
        self.ang_account = ang_account
        
    async def send(
            self, 
            ctx:commands.Context
    ) -> None:
        """Send the view using the discord context
        
        Args:
            ctx (commands.Context): Discord context
        """
        self.message = await ctx.send(content="Chargement du compte...", view=self)
        await self.message.delete()
        self.message = await ctx.send(embed=await self.gen_embed(), view=self)


    async def gen_embed(
            self
    ) -> discord.Embed:
        """Generate the embed for the view
        
        Returns :
            discord.Embed : Discord embed instance 
        """
        embed = discord.Embed(
            title=f"Compte {self.member.guild.name}",
            description=f"**{self.member.name}**\nCompte créé le {self.ang_account.dbcreated_at.strftime('%d/%m/%Y à %Hh%M')}",
        )
        
        return embed