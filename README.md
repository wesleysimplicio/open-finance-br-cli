![open-finance-br-cli — visão geral do projeto](https://v3b.fal.media/files/b/0a9b9c64/6tbp6g6zdvsJPuEz3FkY2_1iCCEv35.png)

# open-finance-br-cli 🏦

CLI para Open Finance Brasil — conectividade bancária padronizada

Além do CLI, este projeto inclui uma **skill Hermes** para que agentes de IA possam executar essas ações via linguagem natural, usando a mesma base de comandos.

## O que já foi feito aqui

Este repositório já passou pela primeira camada de estruturação para agentes e engenharia:

- mapeamento com `llm-project-mapper`
- arquivos de contexto para agentes: `AGENTS.md`, `CLAUDE.md`, `INIT.md`
- estrutura de apoio com `.agents/`, `.skills/` e `.specs/`
- README reorganizado para leitura humana e por agentes
- documentação orientada a onboarding, API e uso prático
- imagem temática no topo para identificação rápida do projeto
- repositório público sincronizado no GitHub

## Automação vs equipe humana

A comparação abaixo é uma **estimativa conservadora** para a fase de descoberta, documentação e padronização inicial.

| Abordagem | Pessoas típicas | Tempo de setup inicial | Observações |
|---|---:|---:|---|
| Time manual | PM + engenheiro(a) + QA + DevOps + técnico(a) de documentação | 2 a 5 dias úteis | exige alinhamento, reuniões e revisão cruzada |
| Fluxo automatizado | 1 engenheiro(a) orquestrando agentes | 1 a 3 horas | reaproveita contexto, reduz retrabalho e padroniza saída |

**Economia estimada:** entre **70% e 90%** do tempo de setup e documentação inicial, dependendo do estado original do projeto.

## Para engenheiros e mantenedores

Se você vai continuar evoluindo este projeto:

1. Leia `AGENTS.md` antes de editar qualquer coisa.
2. Use a skill **`open-finance-br`** para entender o vocabulário e os fluxos esperados.
3. Mantenha o README, a skill e a implementação sincronizados.
4. Prefira mudanças pequenas, auditáveis e fáceis de revisar.
5. Não exponha credenciais, tokens ou dados de sessão.
6. Quando fizer uma mudança relevante, atualize também a documentação de API e os exemplos de uso.

## Visão geral

- **Nome do pacote:** `open-finance-br-cli`
- **Comando instalado:** `openfinance`
- **Runtime:** Python 3.9+
- **API base:** `https://api.openfinance.br (ou sandbox)`
- **Documentação da API:** https://openfinancebrasil.org.br/
- **Endpoints mapeados:** variam por serviço
- **Auth:** OAuth 2.0 / Client Credentials (padrão Open Finance / bancos)
- **Cache local de sessão:** `~/.hermes2/scripts/open-finance-br-cli/`

## Onboarding para agentes 🤖

Se você é um agente lendo este repositório, siga este fluxo:

1. Leia `AGENTS.md` antes de editar qualquer coisa.
2. Use a skill **`open-finance-br`** para entender os fluxos esperados.
3. Evite commitar credenciais; o CLI salva token e config localmente.
4. Prefira mudanças pequenas e verificáveis.
5. Antes de publicar ou automatizar, valide o comportamento real do CLI.

### Skill do Hermes

```python
skill_view(name='open-finance-br')
```

### Regras importantes

- O projeto roda como **CLI + skill**, não como backend web.
- A configuração local fica em `~/.hermes2/scripts/open-finance-br-cli/`.
- O projeto usa a API real do provedor; alguns endpoints dependem de conta/credenciais válidas.

## Recursos principais

- Consentimentos, recursos, dados de usuários, bancos, investimentos
- configuração local com persistência no diretório do usuário
- comandos para consulta e operação via terminal
- integração pensada para agentes e engenheiros
- documentação orientada ao uso prático

## Instalação

### Pré-requisitos

- Python 3.9 ou superior
- Acesso a uma conta válida quando a API exigir autenticação

### Instalar localmente

```bash
git clone https://github.com/wesleysimplicio/open-finance-br-cli.git
cd open-finance-br-cli
pip install -e .
```

### Verificar a instalação

```bash
openfinance --help
```

## Uso rápido

### 1) Abrir ajuda

```bash
openfinance --help
```

### 2) Ler configuração local

```bash
openfinance config show
```

### 3) Ver o caminho do config

```bash
openfinance config path
```

### 4) Ajustar parâmetros locais

```bash
openfinance config set --help
```

Consulte os parâmetros suportados pelo CLI antes de gravar qualquer valor.

## Comandos disponíveis

| Comando | O que faz |
|---|---|
| `openfinance config set` | define base URLs, certificados e credenciais locais |
| `openfinance config show` | mostra a configuração salva |
| `openfinance config path` | mostra o arquivo de configuração usado pelo CLI |
| `openfinance --help` | lista os comandos disponíveis |

## Exemplos úteis

### Listar ajuda

```bash
openfinance --help
```

### Ler configuração local

```bash
openfinance config show
```

### Ver caminho do config

```bash
openfinance config path
```

## Integração com agentes

### Hermes Agent

A skill `open-finance-br` permite que o Hermes execute ações como:

- consultar dados e status
- listar e validar configurações
- operar fluxos permitidos pela API
- registrar saída legível para revisão humana

### Claude Code / Codex

O CLI também pode ser chamado diretamente por agentes via subprocesso:

```bash
claude -p "Rode openfinance --help e me diga o que está disponível"
codex -p "Rode openfinance config show e resuma a configuração"
```

## Estrutura do projeto

```text
open-finance-br-cli/
├── <package>/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── client.py
│   └── config.py
├── skill/
│   └── SKILL.md
├── pyproject.toml
├── setup.py
└── README.md
```

## API mapeada

### Base URL

`https://api.openfinance.br (ou sandbox)`

### Autenticação

- Header / token conforme provedor e CLI
- credenciais locais salvas pelo aplicativo quando necessário

### Principais grupos

| Grupo | Exemplos |
|---|---|
| Autenticação | login, logout, token e validação |
| Conta | saldo, extrato e informações da conta |
| Operações | consultas, pagamentos e fluxos suportados |
| Integrações | recursos do provedor e serviços correlatos |
| Configurações | ajustes locais e persistência de sessão |

## Troubleshooting

### Configuração ausente

Se o CLI reclamar de autenticação ou configuração, ajuste os dados locais novamente:

```bash
openfinance config set --help
```

### Erro de conexão

Verifique se o endpoint do provedor está acessível e se as credenciais estão corretas.

### Ajuda do comando

Se não lembrar a sintaxe, rode:

```bash
openfinance --help
```


## Contribuição

1. Crie mudanças pequenas e testáveis.
2. Mantenha o README, a skill e o CLI alinhados.
3. Evite expor tokens, senhas ou dados de sessão.
4. Quando mudar API ou comportamento, atualize exemplos e documentação.

## Licença

MIT.

