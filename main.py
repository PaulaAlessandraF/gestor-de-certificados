
import pymupdf
import csv
import re
import unicodedata
import asyncio
import json

from pathlib import Path
from collections import defaultdict
from statistics import median
from playwright.async_api import async_playwright
from PIL import Image, ImageDraw, ImageFont


# ==========================================================
# CONFIGURAÇÕES GERAIS
# ==========================================================

CAMINHO_PDF = Path("arquivos/exemplo_nomes.pdf")

PASTA_RESULTADO = Path("resultado")
PASTA_DOWNLOADS = PASTA_RESULTADO / "downloads"

ARQUIVO_REPETIDOS = (
    PASTA_RESULTADO / "repetidos_para_conferencia.csv"
)

TOLERANCIA_Y = 25

LARGURA_NAVEGADOR = 1600
ALTURA_NAVEGADOR = 1200
TEMPO_CARREGAMENTO = 5000


# ==========================================================
# PASTAS E ARQUIVOS DE CONFIGURAÇÃO
# ==========================================================

PASTA_CONFIGURACOES = Path("configuracoes")
PASTA_PERFIS = PASTA_CONFIGURACOES / "perfis"

ARQUIVO_PERFIL_ATIVO = (
    PASTA_CONFIGURACOES / "perfil_ativo.json"
)

ARQUIVO_CONFIG = Path("configuracoes.json")

CAMINHO_MODELO = Path("modelos/certificado_vazio.jpg")
CAMINHO_NOMES = Path("entrada/nomes_faltantes.txt")

PASTA_PREENCHIDOS = (
    PASTA_RESULTADO / "certificados_preenchidos"
)


# ==========================================================
# PREPARAÇÃO DAS PASTAS
# ==========================================================

for pasta in [
    PASTA_RESULTADO,
    PASTA_DOWNLOADS,
    PASTA_CONFIGURACOES,
    PASTA_PERFIS,
    Path("arquivos"),
    Path("modelos"),
    Path("entrada"),
    PASTA_PREENCHIDOS,
]:
    pasta.mkdir(parents=True, exist_ok=True)


# ==========================================================
# CONFIGURAÇÕES DO CERTIFICADO
# ==========================================================

POSICAO_NOME_PADRAO = (1754, 1360)

LARGURA_MAXIMA_TEXTO = 2450

TAMANHO_FONTE_INICIAL = 55
TAMANHO_FONTE_MINIMO = 32

COR_NOME = (16, 27, 43)


def carregar_configuracoes():

    if ARQUIVO_CONFIG.exists():

        try:

            dados = json.loads(
                ARQUIVO_CONFIG.read_text(
                    encoding="utf-8"
                )
            )

            posicao = dados.get("posicao_nome", {})

            return (
                int(
                    posicao.get(
                        "x",
                        POSICAO_NOME_PADRAO[0]
                    )
                ),
                int(
                    posicao.get(
                        "y",
                        POSICAO_NOME_PADRAO[1]
                    )
                ),
            )

        except (
            json.JSONDecodeError,
            TypeError,
            ValueError
        ):

            print(
                "Aviso: configurações inválidas. "
                "Usando posição padrão."
            )

    return POSICAO_NOME_PADRAO


def salvar_posicao_nome(x, y):

    dados = {}

    if ARQUIVO_CONFIG.exists():

        try:

            dados = json.loads(
                ARQUIVO_CONFIG.read_text(
                    encoding="utf-8"
                )
            )

        except json.JSONDecodeError:

            dados = {}

    dados["posicao_nome"] = {
        "x": int(x),
        "y": int(y)
    }

    ARQUIVO_CONFIG.write_text(
        json.dumps(
            dados,
            ensure_ascii=False,
            indent=4
        ),
        encoding="utf-8"
    )


POSICAO_NOME = carregar_configuracoes()


# ==========================================================
# FUNÇÕES AUXILIARES
# ==========================================================

def normalizar_telefone(texto):

    return re.sub(r"\D", "", texto)


def normalizar_id(texto):

    texto = texto.upper().replace(" ", "")

    texto = re.sub(
        r"^R(?=ME-)",
        "",
        texto
    )

    return texto


def limpar_nome_arquivo(nome):

    nome = unicodedata.normalize(
        "NFKD",
        str(nome)
    )

    nome = "".join(
        caractere
        for caractere in nome
        if not unicodedata.combining(caractere)
    )

    nome = re.sub(
        r'[<>:"/\\|?*]',
        "",
        nome
    )

    nome = re.sub(
        r"[^\w\s-]",
        "",
        nome
    )

    nome = re.sub(
        r"\s+",
        "_",
        nome.strip()
    )

    return nome or "SEM_NOME"


def agrupar_palavras_por_linha(pagina):

    palavras = pagina.get_text("words")

    linhas = []

    for palavra in sorted(
        palavras,
        key=lambda p: (p[1], p[0])
    ):

        x0, y0, x1, y1, texto = palavra[:5]

        linha_encontrada = None

        for linha in linhas:

            if abs(linha["y"] - y0) <= 1.2:

                linha_encontrada = linha
                break

        if linha_encontrada is None:

            linha_encontrada = {
                "y": y0,
                "palavras": []
            }

            linhas.append(linha_encontrada)

        linha_encontrada["palavras"].append(
            (x0, y0, x1, y1, texto)
        )

    return linhas


def texto_da_coluna(palavras, inicio, fim):

    selecionadas = [

        palavra

        for palavra in palavras

        if palavra[0] >= inicio
        and palavra[2] <= fim

    ]

    selecionadas.sort(
        key=lambda p: p[0]
    )

    return " ".join(
        palavra[4]
        for palavra in selecionadas
    ).strip()


# ==========================================================
# EXTRAÇÃO DOS REGISTROS DO PDF
# ==========================================================

def extrair_registros(documento, perfil=None):

    registros = []

    for numero_pagina, pagina in enumerate(
        documento,
        start=1
    ):

        linhas = agrupar_palavras_por_linha(pagina)

        if perfil:

            colunas = perfil["colunas"]

            faixa_data = tuple(
                colunas["data"]
            )

            faixa_nome = tuple(
                colunas["nome"]
            )

            faixa_telefone = tuple(
                colunas["telefone"]
            )

            faixa_id = tuple(
                colunas["id_certificado"]
            )

        elif numero_pagina in (1, 2):

            faixa_data = (48, 69)
            faixa_nome = (68, 105)
            faixa_telefone = (105, 121)
            faixa_id = (397, 413)

        else:

            faixa_data = (55, 99)
            faixa_nome = (99, 146.5)
            faixa_telefone = (187, 216)
            faixa_id = (424, 461)

        for linha in linhas:

            palavras = linha["palavras"]

            texto_linha = " ".join(
                p[4]
                for p in sorted(
                    palavras,
                    key=lambda p: p[0]
                )
            )

            data_match = re.search(
                r"\d{2}/\d{2}/\d{4}(?:\s+\d{2}:\d{2})?",
                texto_linha
            )

            if not data_match:
                continue

            data = texto_da_coluna(
                palavras,
                *faixa_data
            ) or data_match.group(0)

            nome = texto_da_coluna(
                palavras,
                *faixa_nome
            )

            telefone = texto_da_coluna(
                palavras,
                *faixa_telefone
            )

            identificador_coluna = texto_da_coluna(
                palavras,
                *faixa_id
            )

            encontrado = re.search(
                r"R?ME-\d{4}-\d+",
                identificador_coluna or texto_linha,
                re.IGNORECASE
            )

            identificador = (

                normalizar_id(
                    encontrado.group(0)
                )

                if encontrado

                else ""

            )

            if not telefone:

                telefone_match = re.search(
                    r"(?:\+?55\s*)?(?:\(?\d{2}\)?\s*)?9?\d{4}[-. ]?\d{4}",
                    texto_linha
                )

                telefone = (
                    telefone_match.group(0)
                    if telefone_match
                    else ""
                )

            centro_y = median(
                (p[1] + p[3]) / 2
                for p in palavras
            )

            registros.append({

                "pagina": numero_pagina,

                "y": centro_y,

                "data_hora": data,

                "nome": nome,

                "telefone": normalizar_telefone(
                    telefone
                ),

                "id_certificado": identificador

            })

    return registros


# ==========================================================
# IDENTIFICAÇÃO DE POSSÍVEIS REPETIDOS
# ==========================================================

def identificar_repetidos(registros):

    por_telefone = defaultdict(list)
    por_id = defaultdict(list)

    for registro in registros:

        telefone = registro["telefone"]

        identificador = registro["id_certificado"]

        if telefone:

            por_telefone[telefone].append(
                registro
            )

        if identificador:

            por_id[identificador].append(
                registro
            )

    repetidos = []

    chaves_adicionadas = set()

    def adicionar_grupo(grupo, motivo):

        for registro in grupo:

            chave = (
                registro["pagina"],
                registro["y"],
                motivo
            )

            if chave in chaves_adicionadas:
                continue

            chaves_adicionadas.add(chave)

            repetidos.append({

                "pagina": registro["pagina"],

                "data_hora": registro["data_hora"],

                "nome": registro["nome"],

                "telefone": registro["telefone"],

                "id_certificado": registro["id_certificado"],

                "motivo_conferencia": motivo

            })

    for telefone, grupo in por_telefone.items():

        if len(grupo) > 1:

            adicionar_grupo(
                grupo,
                "Telefone repetido"
            )

    for identificador, grupo in por_id.items():

        if len(grupo) > 1:

            adicionar_grupo(
                grupo,
                "ID Certificado repetido"
            )

    repetidos.sort(
        key=lambda r: (
            r["pagina"],
            r["data_hora"]
        )
    )

    return repetidos


# ==========================================================
# LOCALIZAR REGISTRO CORRESPONDENTE AO LINK
# ==========================================================

def localizar_registro(
    pagina,
    centro_y,
    registros
):

    candidatos = [

        registro

        for registro in registros

        if registro["pagina"] == pagina

    ]

    if not candidatos:
        return None

    mais_proximo = min(

        candidatos,

        key=lambda registro: abs(
            registro["y"] - centro_y
        )

    )

    distancia = abs(
        mais_proximo["y"] - centro_y
    )

    perfil = carregar_perfil_ativo()

    tolerancia = (
        perfil.get("tolerancia_y", TOLERANCIA_Y)
        if perfil
        else TOLERANCIA_Y
    )

    if distancia <= tolerancia:

        return mais_proximo

    return None


# ==========================================================
# EXTRAIR ID DO GOOGLE DRIVE
# ==========================================================

def extrair_id_drive(url):

    padroes = [

        r"[?&]id=([a-zA-Z0-9_-]+)",

        r"/d/([a-zA-Z0-9_-]+)"

    ]

    for padrao in padroes:

        resultado = re.search(
            padrao,
            url
        )

        if resultado:

            return resultado.group(1)

    return None


def criar_url_visualizacao(url):

    identificador = extrair_id_drive(url)

    if not identificador:

        raise ValueError(
            "Não foi possível identificar o ID do Google Drive."
        )

    return (
        f"https://drive.google.com/file/d/"
        f"{identificador}/preview"
    )


# ==========================================================
# CAPTURAR CERTIFICADO COMO JPG
# ==========================================================

async def capturar_certificado(
    navegador,
    url,
    destino
):

    pagina = await navegador.new_page(

        viewport={

            "width": LARGURA_NAVEGADOR,

            "height": ALTURA_NAVEGADOR

        },

        device_scale_factor=2

    )

    try:

        url_visualizacao = criar_url_visualizacao(
            url
        )

        await pagina.goto(

            url_visualizacao,

            wait_until="domcontentloaded",

            timeout=60000

        )

        await pagina.wait_for_timeout(
            TEMPO_CARREGAMENTO
        )

        await pagina.screenshot(

            path=str(destino),

            type="jpeg",

            quality=95,

            full_page=False

        )

        if (
            not destino.exists()
            or destino.stat().st_size == 0
        ):

            raise Exception(
                "A captura não gerou uma imagem válida."
            )

        return True

    finally:

        await pagina.close()


# ==========================================================
# GERENCIAMENTO DOS PERFIS DE RELATÓRIO
# ==========================================================

def carregar_perfil_ativo():

    if not ARQUIVO_PERFIL_ATIVO.exists():
        return None

    try:

        estado = json.loads(
            ARQUIVO_PERFIL_ATIVO.read_text(
                encoding="utf-8"
            )
        )

        arquivo = (
            PASTA_PERFIS / estado["arquivo"]
        )

        perfil = json.loads(
            arquivo.read_text(
                encoding="utf-8"
            )
        )

        colunas = perfil["colunas"]

        obrigatorias = (
            "data",
            "nome",
            "telefone",
            "id_certificado"
        )

        for campo in obrigatorias:

            faixa = colunas[campo]

            if (
                len(faixa) != 2
                or float(faixa[0]) >= float(faixa[1])
            ):

                raise ValueError(
                    f"Faixa inválida para {campo}."
                )

        return perfil

    except (
        OSError,
        KeyError,
        ValueError,
        json.JSONDecodeError
    ) as erro:

        print(
            "Aviso: não foi possível carregar "
            f"o perfil ativo: {erro}"
        )

        return None


def listar_perfis():

    arquivos = sorted(
        PASTA_PERFIS.glob("*.json")
    )

    if not arquivos:

        print("Nenhum perfil cadastrado.")

        return []

    print("\nPerfis cadastrados:")

    for indice, arquivo in enumerate(
        arquivos,
        start=1
    ):

        try:

            perfil = json.loads(
                arquivo.read_text(
                    encoding="utf-8"
                )
            )

            ativo = ""

            if ARQUIVO_PERFIL_ATIVO.exists():

                estado = json.loads(
                    ARQUIVO_PERFIL_ATIVO.read_text(
                        encoding="utf-8"
                    )
                )

                if estado.get("arquivo") == arquivo.name:

                    ativo = " (ATIVO)"

            print(
                f"[{indice}] "
                f"{perfil.get('nome', arquivo.stem)}"
                f"{ativo}"
            )

        except Exception:

            print(
                f"[{indice}] {arquivo.stem} (arquivo inválido)"
            )

    return arquivos


def selecionar_perfil():

    arquivos = listar_perfis()

    if not arquivos:
        return

    escolha = input(
        "\nNúmero do perfil para ativar (Enter cancela): "
    ).strip()

    if not escolha:
        return

    try:

        arquivo = arquivos[
            int(escolha) - 1
        ]

    except (ValueError, IndexError):

        print("Seleção inválida.")

        return

    ARQUIVO_PERFIL_ATIVO.write_text(

        json.dumps(
            {"arquivo": arquivo.name},
            ensure_ascii=False,
            indent=4
        ),

        encoding="utf-8"

    )

    print(
        f"Perfil ativo: {arquivo.stem}"
    )

# ==========================================================
# APAGAR PERFIL 
# ==========================================================

def apagar_perfil():
    arquivos = listar_perfis()

    if not arquivos:
        return

    escolha = input(
        "\nNúmero do perfil para apagar (Enter cancela): "
    ).strip()

    if not escolha:
        print("Operação cancelada.")
        return

    try:
        arquivo = arquivos[int(escolha) - 1]
    except (ValueError, IndexError):
        print("Seleção inválida.")
        return

    print(f"\nPerfil selecionado: {arquivo.stem}")

    confirmacao = input(
        "Tem certeza que deseja apagar este perfil? (S/N): "
    ).strip().upper()

    if confirmacao != "S":
        print("Exclusão cancelada.")
        return

    # Verifica se o perfil apagado é o perfil ativo.
    if ARQUIVO_PERFIL_ATIVO.exists():
        try:
            estado = json.loads(
                ARQUIVO_PERFIL_ATIVO.read_text(
                    encoding="utf-8"
                )
            )

            if estado.get("arquivo") == arquivo.name:
                ARQUIVO_PERFIL_ATIVO.unlink()
                print("Perfil ativo removido da configuração.")

        except (OSError, json.JSONDecodeError):
            print("Aviso: não foi possível verificar o perfil ativo.")

    try:
        arquivo.unlink()
        print(f"\nPerfil '{arquivo.stem}' apagado com sucesso!")

    except OSError as erro:
        print(f"\nNão foi possível apagar o perfil: {erro}")


# ==========================================================
# CRIAR PERFIL DE RELATÓRIO
# ==========================================================

def configurar_perfil_relatorio():

    try:

        import tkinter as tk

        from tkinter import (
            filedialog,
            messagebox,
            simpledialog
        )

        from PIL import ImageTk

    except ImportError as erro:

        print(
            "Não foi possível iniciar a interface visual: "
            f"{erro}"
        )

        return

    raiz = tk.Tk()

    raiz.withdraw()

    caminho_pdf = filedialog.askopenfilename(

        title="Selecione um PDF de exemplo",

        initialdir=str(
            Path("arquivos").resolve()
        ),

        filetypes=[
            ("Arquivos PDF", "*.pdf")
        ]

    )

    if not caminho_pdf:

        raiz.destroy()

        print("Configuração cancelada.")

        return

    nome_perfil = simpledialog.askstring(

        "Novo perfil",

        "Dê um nome para este perfil de relatório:",

        parent=raiz

    )

    if (
        not nome_perfil
        or not nome_perfil.strip()
    ):

        raiz.destroy()

        print("Nome do perfil não informado.")

        return

    nome_perfil = nome_perfil.strip()

    try:

        documento = pymupdf.open(
            caminho_pdf
        )

        if len(documento) == 0:

            raise ValueError(
                "O PDF não possui páginas."
            )

        pagina_pdf = documento[0]

        largura_pdf = pagina_pdf.rect.width

        altura_pdf = pagina_pdf.rect.height

        pix = pagina_pdf.get_pixmap(

            matrix=pymupdf.Matrix(1.5, 1.5),

            alpha=False

        )

        imagem = Image.frombytes(

            "RGB",

            [pix.width, pix.height],

            pix.samples

        )

        documento.close()

    except Exception as erro:

        raiz.destroy()

        messagebox.showerror(
            "Erro ao abrir PDF",
            str(erro)
        )

        return

    limite_largura = 1100

    limite_altura = 720

    fator = min(

        limite_largura / imagem.width,

        limite_altura / imagem.height,

        1

    )

    tamanho = (

        int(imagem.width * fator),

        int(imagem.height * fator)

    )

    imagem = imagem.resize(tamanho)

    escala_pdf_para_tela = (

        tamanho[0] / largura_pdf,

        tamanho[1] / altura_pdf

    )

    # As cinco colunas que o usuário deve selecionar.

    campos = [

        ("data", "DATA"),

        ("nome", "NOME"),

        ("telefone", "TELEFONE"),

        ("id_certificado", "ID DO CERTIFICADO"),

        ("link", "LINK DO CERTIFICADO")

    ]

    faixas = {}

    indice_atual = {"valor": 0}

    inicio = {"x": None}

    retangulo_id = {"valor": None}

    janela = tk.Toplevel(raiz)

    janela.title(
        f"Configurar perfil: {nome_perfil}"
    )

    janela.geometry("1200x850")

    janela.minsize(850, 600)

    instrucoes = tk.Label(

        janela,

        text=(
            "Arraste o mouse sobre a largura da coluna indicada. "
            "A altura não importa."
        ),

        font=("Arial", 11),

        pady=10

    )

    instrucoes.pack()

    status = tk.Label(

        janela,

        text="",

        font=("Arial", 12, "bold"),

        pady=6

    )

    status.pack()

    canvas = tk.Canvas(

        janela,

        width=tamanho[0],

        height=tamanho[1],

        cursor="cross",

        bg="white",

        scrollregion=(
            0,
            0,
            tamanho[0],
            tamanho[1]
        )

    )

    canvas.pack(
        padx=10,
        pady=5
    )

    foto = ImageTk.PhotoImage(
        imagem
    )

    canvas.create_image(

        0,
        0,

        anchor="nw",

        image=foto

    )

    canvas.image = foto

    rodape = tk.Label(

        janela,

        text=(
            "Selecione do início ao fim da coluna, "
            "evitando invadir a coluna vizinha."
        ),

        pady=8

    )

    rodape.pack()

    def atualizar_status():

        campo, rotulo = campos[
            indice_atual["valor"]
        ]

        status.config(

            text=(
                f"Etapa {indice_atual['valor'] + 1}/5 "
                f"— selecione a coluna: {rotulo}"
            )

        )

    def ao_pressionar(evento):

        inicio["x"] = max(

            0,

            min(
                tamanho[0],
                evento.x
            )

        )

        if retangulo_id["valor"] is not None:

            canvas.delete(
                retangulo_id["valor"]
            )

        retangulo_id["valor"] = canvas.create_rectangle(

            inicio["x"],
            5,

            inicio["x"],
            tamanho[1] - 5,

            outline="red",

            width=3

        )

    def ao_arrastar(evento):

        if inicio["x"] is None:
            return

        x_atual = max(

            0,

            min(
                tamanho[0],
                evento.x
            )

        )

        canvas.coords(

            retangulo_id["valor"],

            inicio["x"],
            5,

            x_atual,
            tamanho[1] - 5

        )

    def ao_soltar(evento):

        if inicio["x"] is None:
            return

        x0_tela = min(

            inicio["x"],

            max(
                0,
                min(tamanho[0], evento.x)
            )

        )

        x1_tela = max(

            inicio["x"],

            max(
                0,
                min(tamanho[0], evento.x)
            )

        )

        if x1_tela - x0_tela < 5:

            messagebox.showwarning(

                "Seleção pequena",

                "Arraste para selecionar a largura da coluna."

            )

            return

        x0_pdf = (
            x0_tela / escala_pdf_para_tela[0]
        )

        x1_pdf = (
            x1_tela / escala_pdf_para_tela[0]
        )

        campo, rotulo = campos[
            indice_atual["valor"]
        ]

        faixas[campo] = [

            round(x0_pdf, 2),

            round(x1_pdf, 2)

        ]

        inicio["x"] = None

        indice_atual["valor"] += 1

        if indice_atual["valor"] == len(campos):

            nome_arquivo = re.sub(

                r"[^a-zA-Z0-9_-]+",

                "_",

                nome_perfil

            ).strip("_").lower()

            if not nome_arquivo:

                nome_arquivo = "perfil_relatorio"

            destino = (
                PASTA_PERFIS /
                f"{nome_arquivo}.json"
            )

            perfil = {

                "nome": nome_perfil,

                "arquivo_exemplo": Path(
                    caminho_pdf
                ).name,

                "colunas": faixas,

                "tolerancia_y": 25,

                "observacao": (
                    "As faixas X são aplicadas às páginas "
                    "do relatório. Revise se o layout mudar."
                )

            }

            destino.write_text(

                json.dumps(
                    perfil,
                    ensure_ascii=False,
                    indent=4
                ),

                encoding="utf-8"

            )

            ARQUIVO_PERFIL_ATIVO.write_text(

                json.dumps(

                    {"arquivo": destino.name},

                    ensure_ascii=False,

                    indent=4

                ),

                encoding="utf-8"

            )

            messagebox.showinfo(

                "Perfil salvo",

                (
                    f"Perfil '{nome_perfil}' salvo e ativado.\n\n"
                    f"Arquivo: {destino}"
                )

            )

            janela.destroy()

            raiz.destroy()

            return

        atualizar_status()

        if retangulo_id["valor"] is not None:

            canvas.delete(
                retangulo_id["valor"]
            )

            retangulo_id["valor"] = None

    canvas.bind(
        "<ButtonPress-1>",
        ao_pressionar
    )

    canvas.bind(
        "<B1-Motion>",
        ao_arrastar
    )

    canvas.bind(
        "<ButtonRelease-1>",
        ao_soltar
    )

    atualizar_status()

    janela.protocol(

        "WM_DELETE_WINDOW",

        lambda: (
            janela.destroy(),
            raiz.destroy()
        )

    )

    raiz.mainloop()


# ==========================================================
# PROCESSAMENTO PRINCIPAL
# ==========================================================

async def baixar_certificados():

    documento = pymupdf.open(
        CAMINHO_PDF
    )

    try:

        perfil_ativo = carregar_perfil_ativo()

        registros = extrair_registros(
            documento,
            perfil_ativo
        )

        repetidos = identificar_repetidos(
            registros
        )

        # ----------------------------------------------
        # GERAR CSV DE REPETIDOS
        # ----------------------------------------------

        with open(

            ARQUIVO_REPETIDOS,

            "w",

            newline="",

            encoding="utf-8-sig"

        ) as arquivo:

            campos = [

                "pagina",

                "data_hora",

                "nome",

                "telefone",

                "id_certificado",

                "motivo_conferencia"

            ]

            escritor = csv.DictWriter(

                arquivo,

                fieldnames=campos,

                delimiter=";"

            )

            escritor.writeheader()

            escritor.writerows(
                repetidos
            )

        # ----------------------------------------------
        # INICIAR NAVEGADOR
        # ----------------------------------------------

        contador_nomes = defaultdict(int)

        links_processados = set()

        total_links = 0

        sucessos = 0

        erros = 0

        print("\n======================================")

        print("       DOWNLOAD DOS CERTIFICADOS")

        print("======================================\n")

        async with async_playwright() as playwright:

            navegador = await playwright.chromium.launch(
                headless=True
            )

            try:

                for numero_pagina, pagina_pdf in enumerate(

                    documento,

                    start=1

                ):

                    links = pagina_pdf.get_links()

                    for item in links:

                        url = item.get("uri")

                        if not url:
                            continue

                        id_drive = extrair_id_drive(
                            url
                        )

                        chave_link = (
                            id_drive
                            or url.strip()
                        )

                        if chave_link in links_processados:
                            continue

                        # Verifica se o link já foi processado.

                        retangulo = pymupdf.Rect(
                            item["from"]
                        )

                        # Verifica se o link está na coluna configurada.

                        if perfil_ativo:

                            faixa_link = (
                                perfil_ativo
                                .get("colunas", {})
                                .get("link")
                            )

                            if faixa_link:

                                centro_x = (
                                    retangulo.x0
                                    + retangulo.x1
                                ) / 2

                                if not (
                                    faixa_link[0]
                                    <= centro_x
                                    <= faixa_link[1]
                                ):

                                    continue

                        links_processados.add(
                            chave_link
                        )

                        total_links += 1

                        centro_y = (

                            retangulo.y0
                            + retangulo.y1

                        ) / 2

                        registro = localizar_registro(

                            numero_pagina,

                            centro_y,

                            registros

                        )

                        if (
                            registro
                            and registro["nome"]
                        ):

                            nome = limpar_nome_arquivo(
                                registro["nome"]
                            )

                        else:

                            nome = "SEM_NOME"

                        contador_nomes[nome] += 1

                        ocorrencia = contador_nomes[nome]

                        if ocorrencia == 1:

                            nome_arquivo = nome

                        else:

                            nome_arquivo = (
                                f"{nome}_{ocorrencia:02d}"
                            )

                        destino = (

                            PASTA_DOWNLOADS
                            / f"{nome_arquivo}.jpg"

                        )

                        print(

                            f"[{total_links}] "

                            f"Página {numero_pagina}: "

                            f"{nome_arquivo}.jpg"

                        )

                        try:

                            await capturar_certificado(

                                navegador,

                                url,

                                destino

                            )

                            sucessos += 1

                            print(
                                "  JPG capturado com sucesso.\n"
                            )

                        except Exception as erro:

                            erros += 1

                            print(
                                f"  Erro: {erro}\n"
                            )

            finally:

                await navegador.close()

        # ----------------------------------------------
        # RESUMO
        # ----------------------------------------------

        print("\n======================================")

        print("             RESUMO FINAL")

        print("======================================")

        print(
            f"Registros extraídos: {len(registros)}"
        )

        print(
            f"Possíveis repetidos: {len(repetidos)}"
        )

        print(
            f"Links encontrados: {total_links}"
        )

        print(
            f"JPGs capturados: {sucessos}"
        )

        print(
            f"Falhas: {erros}"
        )

        print("\nArquivos gerados:")

        print(
            f"- {ARQUIVO_REPETIDOS}"
        )

        print(
            f"- {PASTA_DOWNLOADS}"
        )

        print("\nProcessamento concluído!")

    finally:

        documento.close()


# ==========================================================
# LOCALIZAR FONTE PARA PREENCHIMENTO
# ==========================================================

def localizar_fonte():

    fontes = [

        Path("C:/Windows/Fonts/arialbd.ttf"),

        Path("C:/Windows/Fonts/Arial.ttf"),

        Path(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        ),

    ]

    for fonte in fontes:

        if fonte.exists():

            return str(fonte)

    raise FileNotFoundError(
        "Não encontrei Arial Bold ou DejaVu Sans Bold."
    )


def fonte_ajustada(
    desenho,
    nome,
    caminho_fonte
):

    tamanho = TAMANHO_FONTE_INICIAL

    while tamanho >= TAMANHO_FONTE_MINIMO:

        fonte = ImageFont.truetype(
            caminho_fonte,
            tamanho
        )

        caixa = desenho.textbbox(
            (0, 0),
            nome,
            font=fonte
        )

        largura = (
            caixa[2] - caixa[0]
        )

        if largura <= LARGURA_MAXIMA_TEXTO:

            return fonte

        tamanho -= 2

    return ImageFont.truetype(

        caminho_fonte,

        TAMANHO_FONTE_MINIMO

    )


# ==========================================================
# PREENCHER CERTIFICADOS COM NOMES
# ==========================================================

def preencher_certificados():

    if not CAMINHO_MODELO.exists():

        print(
            f"Modelo não encontrado: {CAMINHO_MODELO}"
        )

        return

    if not CAMINHO_NOMES.exists():

        print(
            f"Crie o arquivo: {CAMINHO_NOMES}"
        )

        return

    nomes = [

        linha.strip()

        for linha in CAMINHO_NOMES.read_text(
            encoding="utf-8-sig"
        ).splitlines()

        if (
            linha.strip()
            and not linha.lstrip().startswith("#")
        )

    ]

    if not nomes:

        print("A lista de nomes está vazia.")

        return

    PASTA_PREENCHIDOS.mkdir(
        parents=True,
        exist_ok=True
    )

    caminho_fonte = localizar_fonte()

    ocorrencias = defaultdict(int)

    for indice, nome_original in enumerate(
        nomes,
        start=1
    ):

        nome = nome_original.upper()

        base_nome = limpar_nome_arquivo(
            nome
        )

        ocorrencias[base_nome] += 1

        nome_arquivo = base_nome

        if ocorrencias[base_nome] > 1:

            nome_arquivo += (
                f"_{ocorrencias[base_nome]:02d}"
            )

        destino = (
            PASTA_PREENCHIDOS
            / f"{nome_arquivo}.jpg"
        )

        imagem = Image.open(
            CAMINHO_MODELO
        ).convert("RGB")

        desenho = ImageDraw.Draw(
            imagem
        )

        fonte = fonte_ajustada(

            desenho,

            nome,

            caminho_fonte

        )

        desenho.text(

            POSICAO_NOME,

            nome,

            font=fonte,

            fill=COR_NOME,

            anchor="mm",

            stroke_width=2,

            stroke_fill=COR_NOME

        )

        imagem.save(

            destino,

            "JPEG",

            quality=95,

            optimize=True

        )

        print(
            f"[{indice}/{len(nomes)}] Criado: {destino.name}"
        )

    print(
        f"\nConcluído. Confira: {PASTA_PREENCHIDOS}"
    )


# ==========================================================
# VERIFICAR TAMANHO DO MODELO VAZIO
# ==========================================================

def verificar_tamanho_modelo():

    if not CAMINHO_MODELO.exists():

        print(
            f"\nModelo vazio não encontrado: {CAMINHO_MODELO}"
        )

        print(
            "Coloque o JPG do certificado na pasta modelos."
        )

        return

    try:

        with Image.open(
            CAMINHO_MODELO
        ) as imagem:

            largura, altura = imagem.size

            print("\n======================================")

            print("       DIMENSÕES DO MODELO VAZIO")

            print("======================================")

            print(
                f"Arquivo: {CAMINHO_MODELO}"
            )

            print(
                f"Formato: {imagem.format}"
            )

            print(
                f"Dimensões: {largura} x {altura} pixels"
            )

            print(
                f"Posição atual do nome: "
                f"X={POSICAO_NOME[0]}, Y={POSICAO_NOME[1]}"
            )

            print(
                "Origem das coordenadas: canto superior esquerdo."
            )

    except Exception as erro:

        print(
            f"Não foi possível abrir o modelo: {erro}"
        )


# ==========================================================
# CONFIGURAR POSIÇÃO DO NOME
# ==========================================================

def configurar_posicao_nome():

    global POSICAO_NOME

    if not CAMINHO_MODELO.exists():

        print(
            f"Modelo vazio não encontrado: {CAMINHO_MODELO}"
        )

        return

    with Image.open(
        CAMINHO_MODELO
    ) as imagem:

        largura, altura = imagem.size

    print("\n======================================")

    print("       CONFIGURAR POSIÇÃO DO NOME")

    print("======================================")

    print(
        f"Modelo: {largura} x {altura} pixels"
    )

    print(
        "X: posição horizontal (0 = esquerda)"
    )

    print(
        "Y: posição vertical (0 = topo)"
    )

    print(
        f"Posição atual: X={POSICAO_NOME[0]}, Y={POSICAO_NOME[1]}"
    )

    print(
        "Dica: para centralizar, comece com metade da largura e metade da altura."
    )

    try:

        entrada_x = input(
            f"Nova posição X [{POSICAO_NOME[0]}]: "
        ).strip()

        entrada_y = input(
            f"Nova posição Y [{POSICAO_NOME[1]}]: "
        ).strip()

        x = (
            int(entrada_x)
            if entrada_x
            else POSICAO_NOME[0]
        )

        y = (
            int(entrada_y)
            if entrada_y
            else POSICAO_NOME[1]
        )

    except ValueError:

        print(
            "Digite apenas números inteiros. "
            "Configuração não alterada."
        )

        return

    if not (
        0 <= x <= largura
        and 0 <= y <= altura
    ):

        print(
            f"Posição inválida. X deve estar entre 0 e {largura}; "
            f"Y entre 0 e {altura}."
        )

        return

    salvar_posicao_nome(
        x,
        y
    )

    POSICAO_NOME = (
        x,
        y
    )

    print(
        f"Posição salva: X={x}, Y={y}"
    )

    print(
        f"Configuração armazenada em: {ARQUIVO_CONFIG}"
    )


# ==========================================================
# MENU PRINCIPAL
# ==========================================================

def iniciar():

    while True:

        print("\n======================================")

        print("       GESTOR DE CERTIFICADOS")

        print("======================================")

        print("[1] Baixar certificados do PDF")

        print("[2] Preencher nomes faltantes")

        print("[3] Verificar tamanho do modelo vazio")

        print("[4] Configurar posição do nome")

        print("[5] Criar novo perfil de relatório")

        print("[6] Ativar perfil de relatório")

        print("[7] Apagar perfil de relatório")

        print("[8] Sair")

        opcao = input(
            "\nEscolha uma opção: "
        ).strip()

        if opcao == "1":

            if not CAMINHO_PDF.exists():

                print(
                    f"PDF não encontrado: {CAMINHO_PDF}"
                )

                print(
                    "Coloque o PDF na pasta arquivos "
                    "ou ajuste CAMINHO_PDF no início do código."
                )

                continue

            try:

                asyncio.run(
                    baixar_certificados()
                )

            except PermissionError as erro:

                print(
                    "\nSem permissão para gravar um arquivo de resultado."
                )

                print(
                    "Feche o CSV no Excel e tente novamente."
                )

                print(
                    f"Detalhe: {erro}"
                )

            except Exception as erro:

                print(
                    f"\nFalha no processamento: {erro}"
                )

        elif opcao == "2":
            preencher_certificados()

        elif opcao == "3":
            verificar_tamanho_modelo()

        elif opcao == "4":
            configurar_posicao_nome()

        elif opcao == "5":
            configurar_perfil_relatorio()

        elif opcao == "6":
            selecionar_perfil()

        elif opcao =="7":
            apagar_perfil()

        elif opcao == "8":

            print(
                "Encerrando aplicação."
            )

            break

        else:

            print(
                "Opção inválida."
            )


# ==========================================================
# EXECUÇÃO
# ==========================================================

if __name__ == "__main__":

    iniciar()
