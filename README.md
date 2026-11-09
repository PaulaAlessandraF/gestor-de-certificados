# Automatizador de Certificados

Aplicação desenvolvida em Python para automatizar tarefas relacionadas à emissão e organização de certificados.

O projeto permite extrair informações de relatórios em PDF, localizar links de certificados armazenados no Google Drive, realizar a captura dos arquivos em JPG e preencher certificados em branco com nomes de uma lista.

Também conta com um sistema de perfis de relatório, permitindo configurar diferentes layouts de PDF sem precisar alterar o código a cada novo formato.

O repositório acompanha arquivos de exemplo utilizados durante os testes, incluindo relatórios em PDF, modelos de certificados, perfis de configuração e resultados gerados pela aplicação. Dessa forma, além do código-fonte, o projeto oferece uma demonstração prática de funcionamento, permitindo que outras pessoas explorem os arquivos, compreendam o fluxo de processamento e testem suas funcionalidades.

## Funcionalidades

- **Download de certificados:** identifica links do Google Drive presentes no relatório PDF e captura os certificados em formato JPG.
- **Extração de dados:** identifica data, nome, telefone e ID do certificado.
- **Identificação de possíveis duplicidades:** verifica telefones e IDs repetidos e gera um arquivo CSV para conferência.
- **Perfis de relatório:** permite configurar as posições das colunas de diferentes modelos de relatório.
- **Gerenciamento de perfis:** permite criar, ativar e excluir perfis cadastrados.
- **Preenchimento de certificados:** insere nomes em um modelo de certificado vazio e gera arquivos JPG individuais.
- **Configuração de posicionamento:** permite ajustar a posição do nome no certificado.

## Tecnologias utilizadas

- Python
- PyMuPDF — leitura e extração de informações dos PDFs.
- Playwright — automação do navegador para captura dos certificados.
- Pillow — manipulação e edição de imagens.
- Tkinter — interface visual para configuração dos perfis.

## Estrutura do projeto

```text
gestor-de-certificados/
│
├── arquivos/
│   └── exemplo_nomes.pdf
│
├── configuracoes/
│   ├── perfis/
│   └── perfil_ativo.json
│
├── entrada/
│   └── nomes_faltantes.txt
│
├── modelos/
│   └── certificado_vazio.jpg
│
├── resultado/
│   ├── downloads/
│   ├── certificados_preenchidos/
│   └── repetidos_para_conferencia.csv
│
├── main.py
├── configuracoes.json
├── requirements.txt
└── README.md
```

## Instalação

É necessário ter o Python instalado na máquina.

Clone o repositório:

```bash
git clone URL_DO_REPOSITORIO
```

Entre na pasta do projeto:

```bash
cd gestor-de-certificados
```

Crie um ambiente virtual:

```bash
python -m venv .venv
```

Ative o ambiente virtual no Windows:

```bash
.venv\Scripts\activate
```

Instale as dependências:

```bash
pip install -r requirements.txt
```

Instale o navegador Chromium utilizado pelo Playwright:

```bash
python -m playwright install chromium
```

## Como utilizar

Execute a aplicação:

```bash
python main.py
```

O programa apresenta um menu com as seguintes opções:

| Opção | Funcionalidade                    |
| ----- | --------------------------------- |
| 1     | Baixar certificados do PDF        |
| 2     | Preencher nomes faltantes         |
| 3     | Verificar tamanho do modelo vazio |
| 4     | Configurar posição do nome        |
| 5     | Criar novo perfil de relatório    |
| 6     | Ativar perfil de relatório        |
| 7     | Apagar perfil de relatório        |
| 8     | Sair                              |

### Download de certificados

Coloque o relatório PDF na pasta `arquivos`, utilizando o caminho configurado em `CAMINHO_PDF`, no início do arquivo `main.py`.

O relatório deve conter links clicáveis do Google Drive associados aos certificados.

Ao executar a opção de download, o programa:

1. Lê os registros do relatório.
2. Identifica possíveis telefones e IDs duplicados.
3. Localiza os links dos certificados.
4. Relaciona os links aos registros correspondentes.
5. Captura os certificados em JPG.
6. Salva os arquivos na pasta `resultado/downloads`.

Os possíveis registros duplicados são exportados para `resultado/repetidos_para_conferencia.csv`.

### Configuração de perfis

Cada empresa pode utilizar um formato diferente de relatório.

Para evitar alterações manuais no código, o programa permite criar perfis personalizados.

Durante a configuração, o usuário seleciona visualmente cinco colunas:

- Data
- Nome
- Telefone
- ID do certificado
- Link do certificado

As configurações são salvas em arquivos JSON dentro de `configuracoes/perfis`.

Depois de criado, o perfil pode ser ativado ou excluído pelo próprio menu.

### Preenchimento de certificados

Coloque a imagem do certificado sem nome na pasta `modelos`.

Adicione os nomes desejados, um por linha, no arquivo:

```text
entrada/nomes_faltantes.txt
```

Execute a opção 2 para gerar os certificados preenchidos.

Os arquivos serão salvos em:

```text
resultado/certificados_preenchidos/
```

A posição do nome pode ser ajustada pela opção 4 do menu.

## Observações

- O projeto foi desenvolvido inicialmente para relatórios com estrutura tabular e links do Google Drive.
- Os perfis permitem adaptar as posições das colunas, mas mudanças significativas no formato do documento podem exigir uma nova configuração.
- Os certificados capturados dependem de links válidos e de acesso permitido no Google Drive.
- O arquivo CSV deve estar fechado em outros programas, como o Excel, durante a gravação dos resultados.

## Objetivo do projeto

## Objetivo do projeto

Este projeto nasceu da minha experiência trabalhando com design gráfico e da vivência com processos que envolvem a produção e a organização de grandes volumes de certificados.

No dia a dia, percebi quanto tempo pode ser consumido por tarefas repetitivas, como localizar arquivos, conferir informações, identificar registros duplicados e organizar certificados individualmente.

Pensando nisso, desenvolvi o Gestor de Certificados: uma ferramenta criada para facilitar a rotina de designers, profissionais de gráficas e equipes que trabalham com grandes quantidades de certificados.

A ideia é transformar etapas manuais em processos automatizados, reduzir o tempo gasto em tarefas operacionais e permitir que esses profissionais dediquem mais atenção ao trabalho que realmente exige sua experiência.

Este projeto também representa a aplicação prática dos conhecimentos de Engenharia de Software na resolução de um problema real, unindo minha experiência profissional em design gráfico à minha formação em Engenharia da Computação. A proposta foi construir uma solução funcional, adaptável e reutilizável, pensando não apenas em automatizar uma tarefa, mas em desenvolver uma ferramenta que pudesse atender a diferentes rotinas de trabalho.

---
Desenvolvido em Python.


Desenvolvido por **Paula Alessandra**
--Engenharia de Software--
