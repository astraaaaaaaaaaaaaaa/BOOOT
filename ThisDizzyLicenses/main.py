import discord
from discord.ext import commands
import random
import difflib
import requests
import re
import asyncio
from datetime import datetime

# Bot Configuration
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.reactions = True  # Permite capturar reações
bot = commands.Bot(command_prefix="!", intents=intents)

#EVENTO BOAS VINDAS

@bot.event
async def on_member_join(member):
    """ Envia uma mensagem de boas-vindas no canal específico quando um novo membro entra no servidor """
    canal_boas_vindas = bot.get_channel(1342148954363531386)  # Canal de boas-vindas
    canal_nickname = "<#1342118070692347967>"  # Canal onde o usuário deve enviar o nickname
    canal_regras = "<#1342143359309054023>"  # Canal onde o usuário pode ver as regras

    if canal_boas_vindas:
        mensagem = (
            f"🎉 Seja bem-vindo ao **RDM FPL**, {member.mention}!\n\n"
            f"✅ Envie o seu **nickname** no canal {canal_nickname} para ser devidamente verificado.\n"
            f"📜 Veja as **regras** no canal {canal_regras}.\n"
            f"🎮 **Divirta-se!**"
        )
        await canal_boas_vindas.send(mensagem)
    else:
        print("Erro: Canal de boas-vindas não encontrado.")

#EVENTO DENUNCIAS

# Variáveis de configuração
contador_ticket = 1  # Número inicial do ticket
TICKETS_CATEGORIA_ID = 1342162057218494474  # ID da categoria onde os tickets serão criados
ARQUIVOS_CATEGORIA_ID = 1342163933955493938  # ID da categoria de arquivamento
DENUNCIA_MENSAGEM_ID = 1342165182645932053  # ID da mensagem de denúncia

# IDs dos cargos de Dono, Administrador e Moderador
DONO_ROLE_ID = 1341951626763833385
ADMIN_ROLE_ID = 1342113966620545034
MOD_ROLE_ID = 1342114240105943082

@bot.event
async def on_ready():
    """ Quando o bot estiver pronto, ele adiciona a reação 🎟️ na mensagem de denúncia """
    print(f"✅ {bot.user.name} está online!")

    channel = None
    for guild in bot.guilds:
        channel = discord.utils.get(guild.text_channels, id=DENUNCIA_MENSAGEM_ID)

    if channel:
        try:
            message = await channel.fetch_message(DENUNCIA_MENSAGEM_ID)
            if message:
                # Verifica se já tem a reação antes de adicionar
                if not any(reaction.emoji == "🎟️" for reaction in message.reactions):
                    await message.add_reaction("🎟️")
                print("✅ Reação 🎟️ adicionada à mensagem de denúncia!")
        except Exception as e:
            print(f"⚠️ Erro ao adicionar reação: {e}")



@bot.event
async def on_raw_reaction_add(payload):
    """ Cria um ticket quando um usuário reage com 🎟️ na mensagem específica """
    if payload.message_id != DENUNCIA_MENSAGEM_ID or str(payload.emoji) != "🎟️":
        return

    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        print(f"Erro: Guild não encontrada para ID {payload.guild_id}")
        return

    member = guild.get_member(payload.user_id)
    if member is None:
        print(f"Erro: Membro {payload.user_id} não encontrado na guilda.")
        return

    if member.bot:  # Ignorar bots
        return

    global contador_ticket
    ticket_nome = f"ticket-{str(random.randint(1, 99999)).zfill(5)}"
    contador_ticket += 1  

    # Buscar os cargos corretamente
    dono_role = guild.get_role(DONO_ROLE_ID)
    admin_role = guild.get_role(ADMIN_ROLE_ID)
    mod_role = guild.get_role(MOD_ROLE_ID)

    if not dono_role or not admin_role or not mod_role:
        print("Erro: Um ou mais cargos não foram encontrados!")
        return

    # Definir permissões do canal privado
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),  
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True),  
        dono_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),  
        admin_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),  
        mod_role: discord.PermissionOverwrite(read_messages=True, send_messages=True)  
    }

    # Buscar a categoria correta para criação de tickets
    categoria_tickets = discord.utils.get(guild.categories, id=TICKETS_CATEGORIA_ID)
    if not categoria_tickets:
        print(f"Erro: Categoria de tickets {TICKETS_CATEGORIA_ID} não encontrada!")
        return

    # Criar canal do ticket dentro da categoria correta
    try:
        ticket_channel = await guild.create_text_channel(ticket_nome, category=categoria_tickets, overwrites=overwrites)
        await ticket_channel.send(f"🎫 **Ticket de denúncia criado por {member.mention}**.\n\nDescreva o problema aqui. Um moderador responderá em breve.")

        # Remover a reação do usuário para evitar spam
        channel = bot.get_channel(payload.channel_id)
        if channel:
            message = await channel.fetch_message(payload.message_id)
            await message.remove_reaction(payload.emoji, member)

        # Fecha o ticket automaticamente após 30 minutos sem mensagens
        async def fechar_ticket():
            await asyncio.sleep(1800)  
            if ticket_channel:
                await ticket_channel.delete()

        bot.loop.create_task(fechar_ticket())

    except Exception as e:
        print(f"Erro ao criar o canal de ticket: {e}")

# Comando para arquivar o ticket
@bot.command()
@commands.has_any_role(DONO_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID)
async def arquivar(ctx, *, motivo: str = None):
    """ Arquiva um ticket e remove acesso do denunciante """
    if motivo is None:
        await ctx.send("❌ Você deve fornecer um motivo para arquivar este ticket!")
        return

    if not ctx.channel.name.startswith("ticket-"):
        await ctx.send("❌ Este comando só pode ser usado em canais de ticket!")
        return

    guild = ctx.guild
    categoria_arquivos = discord.utils.get(guild.categories, id=ARQUIVOS_CATEGORIA_ID)

    if not categoria_arquivos:
        await ctx.send("❌ Categoria de arquivamento não encontrada. Verifique o ID!")
        return

    # Remover acesso do denunciante e enviar mensagem privada
    for member in ctx.channel.members:
        if member.id not in [DONO_ROLE_ID, ADMIN_ROLE_ID, MOD_ROLE_ID]:
            await ctx.channel.set_permissions(member, read_messages=False, send_messages=False)

            try:
                data_hora = datetime.now().strftime("%d/%m/%Y %H:%M")
                embed_dm = discord.Embed(title="📁 Seu Ticket foi Arquivado", color=discord.Color.red())
                embed_dm.add_field(name="🎫 Número do Ticket", value=ctx.channel.name, inline=False)
                embed_dm.add_field(name="🛠️ Arquivado por", value=ctx.author.mention, inline=False)
                embed_dm.add_field(name="📅 Data e Hora", value=data_hora, inline=False)
                embed_dm.add_field(name="📌 Motivo", value=motivo, inline=False)
                embed_dm.set_footer(text="Caso precise abrir um novo ticket, reaja novamente.")

                await member.send(embed=embed_dm)
            except:
                print(f"⚠️ Não foi possível enviar DM para {member.name}")

    await ctx.channel.edit(category=categoria_arquivos)
    await ctx.send(f"✅ O ticket foi arquivado e movido para {categoria_arquivos.name}.")

@arquivar.error
async def arquivar_error(ctx, error):
    if isinstance(error, commands.MissingAnyRole):
        await ctx.send("❌ Apenas donos, administradores e moderadores podem arquivar tickets!")

# EVENTO CANAIS DE VOZ TEMPORARIOS

@bot.event
async def on_voice_state_update(member, before, after):
    # ID do canal de voz original
    voice_channel_id = 1341951308277743712
    # Verifica se o membro entrou no canal de voz específico
    if after.channel and after.channel.id == voice_channel_id:
        # Obtém a categoria do canal original
        original_channel = bot.get_channel(voice_channel_id)
        category = original_channel.category
        # Cria um nome para o novo canal
        channel_count = len([c for c in category.voice_channels if c.name.startswith(original_channel.name)]) + 1
        new_channel_name = f"💬 | 𝘽𝙖𝙩𝙚-𝙋𝙖𝙥𝙤 {channel_count}"
        # Cria o novo canal de voz
        new_voice_channel = await category.create_voice_channel(name=new_channel_name)
        # Move o usuário para o novo canal de voz
        await member.move_to(new_voice_channel)
    # Verifica se o membro saiu de um canal de voz
    if before.channel and not after.channel:
        # Verifica se o canal está vazio e ainda existe
        try:
            channel = bot.get_channel(before.channel.id)
            if channel and len(channel.members) == 0:
                await channel.delete()
        except discord.NotFound:
            pass

    # ID do canal de voz original
    voice_channel_id2 = 1342141027326103552
    # Verifica se o membro entrou no canal de voz específico
    if after.channel and after.channel.id == voice_channel_id2:
        # Obtém a categoria do canal original
        original_channel = bot.get_channel(voice_channel_id2)
        category = original_channel.category
        # Cria um nome para o novo canal
        channel_count = len([c for c in category.voice_channels if c.name.startswith(original_channel.name)]) + 1
        new_channel_name = f"🕹 | 𝙍𝙖𝙣𝙠𝙚𝙙"
        # Cria o novo canal de voz
        new_voice_channel = await category.create_voice_channel(name=new_channel_name, user_limit=5)
        # Move o usuário para o novo canal de voz
        await member.move_to(new_voice_channel)
            # Lista de canais fixos que NÃO devem ser excluídos
    FIXED_VOICE_CHANNELS = {1341951308277743712, 1342141027326103552, 1342194009623232532, 1343348236462587934, 1344463028556664852}

    # Verifica se o membro saiu de um canal de voz
    if before.channel and not after.channel:
        try:
            channel = bot.get_channel(before.channel.id)
            # Verifica se o canal está vazio, existe e NÃO está na lista de canais fixos
            if channel and len(channel.members) == 0 and channel.id not in FIXED_VOICE_CHANNELS:
                await channel.delete()
        except discord.NotFound:
            pass

# Game State
class GameState:
    def __init__(self):
        self.jogadores = []
        self.time_azul = []
        self.time_vermelho = []
        self.capitaes = []
        self.bloqueado = False
        self.mapas = [
            "CLUBE HOUSE", "KAFE DOSTOIÉVSKI", "CONSULADO", "LABORATÓRIO",
            "COVIL", "FRONTEIRA", "CHALET", "BANCO", "ARRANHA-CÉU"
        ]
        self.mapas_banidos = []

game = GameState()
MAX_JOGADORES = 10
LOBBY_CHANNEL_ID = 1341953414933905429
STATS_CHANNEL_ID = 1342118070692347967

# Utility Functions
def in_lobby_channel():
    async def predicate(ctx):
        if ctx.channel.id != LOBBY_CHANNEL_ID:
            await ctx.send("🚫 **ESSE COMANDO SÓ PODE SER UTILIZADO NO CANAL PREPARACAO LOBBY** 🚫")
            return False
        return True
    return commands.check(predicate)

def is_admin(ctx):
    return ctx.author.guild_permissions.administrator

# Command Groups
class AdminCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def ver_mapas(self, ctx):
        mapas_disponiveis = [m for m in game.mapas if m not in game.mapas_banidos]
        lista_mapas = '\n\n'.join(
            f'✦  **{"~~" + m + "~~ 🚫" if m in game.mapas_banidos else m}**  ✦'
            for m in game.mapas)

        if len(mapas_disponiveis) == 1:
            mapa_escolhido = mapas_disponiveis[0]
            capitao_escolha = game.capitaes[1] if game.capitaes else "(Capitão Não Definido)"
            await ctx.send(
                f'🔹 **🔥 O MAPA ESCOLHIDO É: 🔥** ✦ {mapa_escolhido} ✦ 🔹\n'
                f'🚀 **{capitao_escolha}, POR GENTILEZA ESCOLHA SE DESEJA COMEÇAR ATACANDO OU DEFENDENDO!** 🚀'
            )
        else:
            await ctx.send(f'**🔍  LISTA DE MAPAS  🔍**\n\n{lista_mapas}')

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def ban(self, ctx, *, mapa: str):
        mapa_proximo = difflib.get_close_matches(mapa.upper(), game.mapas, n=1, cutoff=0.5)

        if not mapa_proximo:
            await ctx.send("❌ MAPA NÃO ENCONTRADO NA LISTA DISPONÍVEL!")
            return

        mapa_escolhido = mapa_proximo[0]
        if mapa_escolhido in game.mapas_banidos:
            await ctx.send(f'⚠️ O MAPA **{mapa_escolhido}** JÁ ESTÁ BANIDO!')
        else:
            game.mapas_banidos.append(mapa_escolhido)
            await ctx.send(f'🚫 O MAPA **{mapa_escolhido}** FOI BANIDO!')

        await self.ver_mapas(ctx)

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def resetar_mapas(self, ctx):
        game.mapas_banidos.clear()
        await ctx.send("✅ A LISTA DE MAPAS FOI RESETADA!")

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def adicionar(self, ctx, jogador: discord.Member):
        if jogador.mention in game.jogadores:
            await ctx.send(f'{jogador.mention} já está na lista!')
            return
        if len(game.jogadores) < MAX_JOGADORES:
            game.jogadores.append(jogador.mention)
            await ctx.send(f'{jogador.mention} foi adicionado à lista! ({len(game.jogadores)}/{MAX_JOGADORES})')
        else:
            await ctx.send('A lista já está cheia!')

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def remover(self, ctx, jogador: discord.Member):
        if jogador.mention in game.jogadores:
            game.jogadores.remove(jogador.mention)
            await ctx.send(f'{jogador.mention} foi removido da lista! ({len(game.jogadores)}/{MAX_JOGADORES})')
        else:
            await ctx.send(f'{jogador.mention} não está na lista!')

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def lista(self, ctx):
        if game.jogadores:
            lista_jogadores = '\n'.join(f'→ {j}' for j in game.jogadores)
            await ctx.send(
                f'Lista de jogadores ({len(game.jogadores)}/{MAX_JOGADORES}):\n{lista_jogadores}'
            )
        else:
            await ctx.send('A LISTA DE JOGADORES ESTA VAZIA.')

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def sortear_capitao(self, ctx):
        if len(game.jogadores) < 2:
            await ctx.send("Não há jogadores suficientes para sortear capitães!")
            return

        game.capitaes = random.sample(game.jogadores, 2)
        await ctx.send(f'👑 NOVOS CAPITÃES: **{game.capitaes[0]}** E **{game.capitaes[1]}**')


class PlayerCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @in_lobby_channel()
    async def jogar(self, ctx):
        if game.bloqueado:
            await ctx.send("❌ NÃO É POSSÍVEL ENTRAR APÓS O INÍCIO! AGUARDE !FINALIZAR.")
            return

        if ctx.author.mention in game.jogadores:
            await ctx.send(f'{ctx.author.mention}, VOCÊ JÁ ESTÁ NA LISTA!')
            return

        if len(game.jogadores) < MAX_JOGADORES:
            game.jogadores.append(ctx.author.mention)
            await ctx.send(
                f'✅  {ctx.author.mention}  ENTROU NA LISTA!  ({len(game.jogadores)}/{MAX_JOGADORES})'
            )
        else:
            await ctx.send(f'{ctx.author.mention}, A LISTA JÁ ESTÁ CHEIA!')

    @commands.command()
    @in_lobby_channel()
    async def sair(self, ctx):
        if game.bloqueado:
            await ctx.send("🚫 VOCÊ NÃO PODE SAIR DO JOGO AGORA!")
            return

        if ctx.author.mention in game.jogadores:
            game.jogadores.remove(ctx.author.mention)
            await ctx.send(
                f'✅ {ctx.author.mention} SAIU DA LISTA! ({len(game.jogadores)}/{MAX_JOGADORES})'
            )

class GameManagement(commands.Cog):
    @commands.command()
    @commands.check(is_admin)
    async def resetar_lista(self, ctx):
        """Reseta a lista de jogadores e times"""
        game.jogadores.clear()
        game.time_azul.clear()
        game.time_vermelho.clear()
        game.capitaes.clear()
        await ctx.send("🔄 A lista de jogadores e os times foram resetados!")
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.check(is_admin)
    @in_lobby_channel()
    async def iniciar(self, ctx):
        if len(game.jogadores) < MAX_JOGADORES:
            await ctx.send("❌ JOGADORES INSUFICIENTES PARA INICIAR!")
            return

        game.bloqueado = True
        game.capitaes = random.sample(game.jogadores, 2)
        game.jogadores = [j for j in game.jogadores if j not in game.capitaes]
        game.time_azul = [game.capitaes[0]]
        game.time_vermelho = [game.capitaes[1]]

        await ctx.send(
            "🔒 ENTRADA DE JOGADORES BLOQUEADA! USE !FINALIZAR PARA LIBERAR NOVAMENTE.\n"
            f"⚔️ **OS CAPITÃES SÃO:** {game.capitaes[0]} e {game.capitaes[1]}\n"
            f"🔵 {game.capitaes[0]} COMEÇA ESCOLHENDO!"
        )

#COMANDO PICK JOGADORES
        class Game:
            def __init__(self):
                self.jogadores = []
                self.time_azul = []
                self.time_vermelho = []
                self.capitaes = []
                self.bloqueado = False

        game = Game()

        def is_admin(ctx):
            return ctx.author.guild_permissions.administrator

        @bot.event
        async def on_ready():
            print(f"Bot conectado como {bot.user}")

        @commands.command()
        async def ver_times(ctx):
            """Mostra a lista dos times Azul e Vermelho"""
            if not game.time_azul and not game.time_vermelho:
                await ctx.send("Os times ainda não foram formados.")
                return

            azul = "\n".join(game.time_azul) if game.time_azul else "Nenhum jogador ainda."
            vermelho = "\n".join(game.time_vermelho) if game.time_vermelho else "Nenhum jogador ainda."

            embed = discord.Embed(title="Times Atuais", color=discord.Color.blue())
            embed.add_field(name="Time Azul 🔵", value=azul, inline=True)
            embed.add_field(name="Time Vermelho 🔴", value=vermelho, inline=True)

            await ctx.send(embed=embed)

        @commands.command()
        @commands.check(is_admin)
        async def escolher(ctx, jogador: discord.Member):
            """Escolhe um jogador e o adiciona a um time"""
            if jogador.mention not in game.jogadores:
                await ctx.send(f'❌ {jogador.mention} não está na lista de jogadores!')
                return

            if len(game.time_azul) <= len(game.time_vermelho):
                game.time_azul.append(jogador.mention)
                time = "🔵 Time Azul"
            else:
                game.time_vermelho.append(jogador.mention)
                time = "🔴 Time Vermelho"

            game.jogadores.remove(jogador.mention)
            await ctx.send(f'✅ {jogador.mention} foi escolhido para o {time}!')

            # Exibir times atualizados
            await ver_times(ctx)

        @commands.command()
        @commands.check(is_admin)
        async def set_captains(ctx, cap1: discord.Member, cap2: discord.Member):
            """Define os capitães e inicia a escolha"""
            game.capitaes = [cap1, cap2]
            game.time_azul = [cap1.mention]
            game.time_vermelho = [cap2.mention]

            await ctx.send(f"Os capitães foram definidos: {cap1.mention} e {cap2.mention}. {cap1.mention}, é sua vez de escolher um jogador!")

        @commands.command()
        @commands.check(is_admin)
        async def finalizar(self, ctx):
            """Finaliza o jogo e reseta as listas"""
            game.bloqueado = False
            game.jogadores.clear()
            game.time_azul.clear()
            game.time_vermelho.clear()
            game.capitaes.clear()
            await ctx.send("🔓 ENTRADA DE JOGADORES LIBERADA NOVAMENTE!")

        @commands.command()
        @commands.check(is_admin)
        async def sortear_times(ctx):
            """Sorteia jogadores aleatoriamente para cada time"""
            if len(game.jogadores) < 2:
                await ctx.send("❌ JOGADORES INSUFICIENTES!")
                return

            random.shuffle(game.jogadores)
            meio = len(game.jogadores) // 2
            game.time_azul = game.jogadores[:meio]
            game.time_vermelho = game.jogadores[meio:]

            await ctx.send(
                f"🎲 **TIMES SORTEADOS!** 🎲\n"
                f"🔹 **TIME AZUL:** {', '.join(game.time_azul)}\n"
                f"🔸 **TIME VERMELHO:** {', '.join(game.time_vermelho)}"
            )

        bot.add_command(ver_times)
        bot.add_command(escolher)
        bot.add_command(set_captains)
        bot.add_command(finalizar)
        bot.add_command(sortear_times)

# Setup
@bot.event
async def setup_hook():
    await bot.add_cog(AdminCommands(bot))
    await bot.add_cog(PlayerCommands(bot))
    await bot.add_cog(GameManagement(bot))

@bot.command()
@in_lobby_channel()
async def comandos(ctx):
    comandos_publicos = [" !jogar - ENTRA NA LISTA DE JOGADORES\n", " !sair - SAI DA LISTA (SE AINDA NÃO INICIOU)\n", "!comandos - LISTA DE COMANDOS\n", "!buscar - BUSCA ESTATÍSTICAS DE UM JOGADOR\n"]
    comandos_admin = [
        " !ver_mapas - VÊ A LISTA DE MAPAS\n", " !ban - BANE UM MAPA\n", " !resetar_mapas - RESETA OS MAPAS\n", " !iniciar - INICIA O JOGO\n", " !finalizar - FINALIZA O JOGO\n", " !sortear_times - SORTEIA ALEATORIAMENTE TIMES\n", " !sortear_capitao - REDEFINE OS CAPITÃES\n", " !adicionar - ADICIONA UM JOGADOR NA LISTA\n", " !remover - REMOVE UM JOGADOR DA LISTA\n", " !lista - VEJA A LISTA DE JOGADORES\n"
    ]

    publicos_formatados = '\n'.join(f'🔹 **{cmd}**'
                                    for cmd in comandos_publicos)
    admins_formatados = '\n'.join(f'🔸 **{cmd}** (ADM)'
                                  for cmd in comandos_admin)

    await ctx.send(
        f"📜 **Lista de Comandos:**\n\n{publicos_formatados}\n{admins_formatados}"
    )

bot.run('MTM0MTkwMTk4OTU4NzcxODIzNA.Gtr78R.ZGdjMU_yJKnNn4gosiE8LwnUtrFAmG-ZFGABAY')