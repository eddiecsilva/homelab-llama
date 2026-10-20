# Homelab Llama

> [!WARNING]
> **Aviso:** este lab foi planejado e testado apenas em ambientes isolados na rede local. Não é indicado para uso em ambientes de produção real.

Ambiente local de IA com 8 serviços Docker: chat com modelos da sua máquina, RAG sobre seus documentos, busca privada, transcrição de áudio e leitura de feeds. Sem nuvem, sem custo de API, sem seus dados saindo de casa.

Homelab Llama reúne 8 serviços de IA em containers Docker que rodam na sua máquina: chat com modelos locais (llama.cpp), três interfaces web para conversar e pesquisar (Open WebUI, AnythingLLM e Vane), transcrição de áudio e vídeo (WhisperX), busca privada (SearXNG) e leitura de feeds (FreshRSS). Nada sai da máquina - modelos, documentos e histórico ficam em disco local, e o único pré-requisio real é uma GPU NVIDIA com o NVIDIA Container Toolkit configurado.

## 📑 Índice

- [Visão geral](#visao-geral)
- [Instalação](#instalacao)
- [Capturas de tela](#capturas-de-tela)
- [Hardware](#hardware)
- [Modelos](#modelos)
- [Acesso e autenticação](#acesso-e-autenticacao)
- [Troubleshooting](#troubleshooting)
- [Links externos](#links-externos)
- [Licença](#licenca)

---

<a id="visao-geral"></a>

## 🚀 Visão Geral

| Serviço | O que faz | Acesso local | Serviço no compose | Site oficial |
|---------|-----------|--------------|--------------------|--------------|
| Open WebUI | Chat, RAG sobre documentos e busca web | http://localhost:3000 | `open-webui` | [openwebui.com](https://openwebui.com) |
| AnythingLLM | Base de conhecimento sobre seus documentos | http://localhost:3001 | `anythingllm` | [anythingllm.com](https://anythingllm.com) |
| Vane | Busca web com resposta e citações | http://localhost:3002 | `vane` | [github.com/ItzCrazyKns/Vane](https://github.com/ItzCrazyKns/Vane) |
| SearXNG | Metabusca privada (agrega vários motores) | http://localhost:8084 | `searxng` | [github.com/searxng/searxng](https://github.com/searxng/searxng) |
| FreshRSS | Leitor de feeds RSS | http://localhost:3003 | `freshrss` | [freshrss.org](https://freshrss.org) |
| WhisperX | Transcrição de áudio/vídeo com timestamps | http://localhost:9000 (API) | `whisperx` | [github.com/m-bain/whisperX](https://github.com/m-bain/whisperX) |
| llama.cpp (GPU) | Servidor do modelo de chat | http://localhost:8085 (API) | `llama-gpu` | [github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) |
| llama.cpp (Embed) | Vetores para RAG | http://localhost:8086 (API) | `llama-embed` | [github.com/ggml-org/llama.cpp](https://github.com/ggml-org/llama.cpp) |

> [!NOTE]
> As portas vêm do `.env` (`OPENWEBUI_PORT`, `VANE_PORT`, `SEARXNG_PORT`, ...) e a tabela segue o `.env.example`. De dentro de outro container, use `host.docker.internal` no lugar de `localhost`.

---

<a id="instalacao"></a>

## 📦 Instalação

### Pré-requisitos

- **Docker** 20.10+ com **Compose Plugin** 2.0+
- **NVIDIA Container Toolkit** (para a GPU) - [guia de instalação](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
- **Windows:** WSL2 com [Docker Desktop](https://www.docker.com/products/docker-desktop)

```bash
# Ubuntu/Debian
sudo apt install docker.io docker-compose-plugin -y
sudo usermod -aG docker $USER && newgrp docker

# Conferir a GPU no container
docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi
```

### Passos

1. **Copiar o template de configuração**

   ```bash
   cd homelab-llama
   cp .env.example .env
   ```

2. **Gerar os secrets criptográficos**

   ```bash
   for k in WEBUI_SECRET_KEY ANYTHINGLLM_SIG_KEY ANYTHINGLLM_SIG_SALT SEARXNG_SECRET FRESHRSS_PASSWORD FRESHRSS_API_PASSWORD; do
     sed -i "s|^$k=.*|$k=$(openssl rand -hex 32)|" .env
   done
   ```

3. **Configurar o SearXNG** (o `settings.yml` não é versionado porque tem o `secret_key`)

   ```bash
   cp config/searxng/settings.example.yml config/searxng/settings.yml
   sed -i "s|^  secret_key: .*|  secret_key: $(openssl rand -hex 32)|" config/searxng/settings.yml
   ```

4. **Subir os serviços**

   ```bash
   docker compose up -d
   docker compose ps
   ```

> [!WARNING]
> O `.env` ainda tem campos em branco para você preencher: `CHAT_MODEL`, `MODELS_DIR` e `FRESHRSS_USERNAME`. Sem modelo em `$MODELS_DIR/chat` o chat não responde.

### Como ficam os nomes dos containers

O Docker Compose monta o nome como `<COMPOSE_PROJECT_NAME>-<serviço>-<número>`, por exemplo `hmlb-cpp-open-webui-1`. O prefixo vem do `.env`, então muda de máquina para máquina.

Nos comandos do Compose use o **nome do serviço** do `compose.yaml` (`open-webui`, `searxng`, `llama-gpu`...). Para ver os nomes reais, com portas e redes de cada container:

```bash
docker ps --format 'table {{.Names}}\t{{.Ports}}\t{{.Networks}}'
```

### Comandos frequentes

```bash
docker compose logs -f              # logs de todos os serviços
docker compose logs -f open-webui   # logs de um serviço
docker compose restart open-webui   # reiniciar um serviço
docker compose down                 # parar (mantém os dados)
docker compose down -v              # remover tudo, inclusive os dados
docker compose pull && docker compose up -d   # atualizar as imagens
```

---

<a id="capturas-de-tela"></a>

## 📸 Capturas de Tela

Na prática o conjunto funciona como uma casa única para IA local: você conversa e faz perguntas em três interfaces diferentes (Open WebUI, AnythingLLM e Vane), todas apoiadas no mesmo modelo GGUF servido pelo llama.cpp e nos mesmos embeddings (bge-m3) para busca semântica nos seus documentos; atrás delas o SearXNG faz a busca na web sem rastrear você, o WhisperX transcreve áudios com marcação de tempo e o FreshRSS concentra os feeds. O Vane junta busca, resposta do modelo e citações; o AnythingLLM mantém bases de conhecimento separadas por workspace.

```mermaid
flowchart TD
    subgraph UI["Interfaces"]
        OWUI["Open WebUI"]
        ANY["AnythingLLM"]
        VANE["Vane"]
    end

    subgraph CORE["llama.cpp"]
        GPU["GPU<br/>chat"]
        EMB["Embed<br/>embeddings"]
    end

    subgraph DATA["Modelos"]
        MODEL[("modelo GGUF")]
        BGE[("bge-m3")]
    end

    subgraph BUSCA["Busca"]
        SEAR["SearXNG<br/>busca privada"]
        WEB(("web"))
    end

    WX["WhisperX<br/>transcricao"]

    OWUI --> GPU
    ANY --> GPU
    VANE --> GPU
    OWUI --> EMB
    ANY --> EMB
    GPU --> MODEL
    EMB --> BGE
    OWUI --> SEAR
    ANY --> SEAR
    VANE --> SEAR
    SEAR --> WEB
    WX --> OWUI

    classDef ui fill:#e8f0fe,stroke:#4285f4,stroke-width:1px,color:#17375e
    classDef llm fill:#fef7e0,stroke:#f9ab00,stroke-width:1px,color:#7a4b00
    classDef model fill:#f3e8fd,stroke:#a142f4,stroke-width:1px,color:#4a1d6b
    classDef search fill:#e6f4ea,stroke:#34a853,stroke-width:1px,color:#1e5b2a
    classDef media fill:#fde8e8,stroke:#ea4335,stroke-width:1px,color:#7a2018

    class OWUI,ANY,VANE ui
    class GPU,EMB llm
    class MODEL,BGE model
    class SEAR,WEB search
    class WX media

    style UI fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#334155
    style CORE fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#334155
    style DATA fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#334155
    style BUSCA fill:#f8fafc,stroke:#cbd5e1,stroke-width:1px,color:#334155
```

*Cada seta indica quem chama quem: as interfaces pedem chat ao llama.cpp, embeddings ao bge-m3 e busca ao SearXNG; o WhisperX entrega transcrição para o Open WebUI.*

## **Open WebUI** - chat, RAG e busca web em uma tela só.

![Open WebUI Interface](screenshots/screenshotopenwebui.png)

## **AnythingLLM** - documentos e bases de conhecimento por workspace.

![AnythingLLM Interface](screenshots/screenshotanythingllm.png)

## **SearXNG** - a busca por trás de tudo, sem rastreamento.

![SearXNG Interface](screenshots/screensharxng.png)

## **Vane** - busca com resposta do modelo e citações.

![Vane Interface](screenshots/screens-vane.png)

## **WhisperX** - não tem interface própria; acompanhe a transcrição pelo log:

```bash
docker compose logs whisperx
```

---

<a id="hardware"></a>

## 💻 Hardware

Testado em: AMD Ryzen 5 5700X (8 núcleos/16 threads), 48GB RAM, NVIDIA RTX 5070 Ti 16GB (CUDA), SSD NVMe 200GB+, Debian 13.

Mínimo para rodar a stack: 8 núcleos, 32GB RAM, GPU NVIDIA 8GB+ VRAM, 100GB livres.

---

<a id="modelos"></a>

## 🤖 Modelos

O stack usa **llama.cpp** em modo router: o modelo carregado é definido por `CHAT_MODEL` no `.env`.

- **Chat:** arquivo GGUF em `$MODELS_DIR/chat` e nome em `CHAT_MODEL`.
- **Embeddings:** modelo baixado automaticamente de `EMBEDDING_HF_REPO` (`bge-m3` por padrão), usado por Open WebUI e AnythingLLM no RAG.

```bash
# Ver modelo carregado e memória usada
docker compose logs -f llama-gpu

# Listar modelos no container
docker compose exec llama-gpu ls /models/chat
```

> [!NOTE]
> Não existe `ollama pull` aqui: os modelos são arquivos GGUF servidos pelo llama.cpp.

---

<a id="acesso-e-autenticacao"></a>

## 🔐 Acesso e Autenticação

| Serviço | Entrar com |
|---------|-----------|
| FreshRSS | usuário `FRESHRSS_USERNAME` e senha `FRESHRSS_PASSWORD` do `.env` |
| AnythingLLM | organize e defina as credenciais administrativas na primeira abertura |
| Open WebUI | crie a conta no primeiro acesso (signup habilitado) |

> [!TIP]
> O container do FreshRSS só cria o usuário na primeira instalação. Depois disso, trocar a senha no `.env` não altera a senha atual - mude pela interface (Configurações > Conta) e ajuste o `.env`.

---

<a id="troubleshooting"></a>

## 🩺 Troubleshooting

```bash
docker compose ps                # quem está de pé
docker compose logs <serviço>    # log de um serviço
nvidia-smi && free -h            # GPU e memória
```

Erros de memória: reduza `LLAMA_MODELS_MAX` e `LLAMA_CTX_SIZE` no `.env`.
Erros de GPU: reinicie o Docker (`sudo systemctl restart docker`) e teste com `docker run --rm --gpus all nvidia/cuda:12.1.0-base-ubuntu22.04 nvidia-smi`.

Os dados ficam em `data/` (bind mount) e em `$MODELS_DIR/` - faça backup antes de mexer.

---

<a id="links-externos"></a>

## 🔗 Links Externos

Documentação de cada serviço:

- Open WebUI - [docs.openwebui.com](https://docs.openwebui.com)
- AnythingLLM - [docs.anythingllm.com](https://docs.anythingllm.com)
- Vane - [discussions no GitHub](https://github.com/ItzCrazyKns/Vane/discussions)
- SearXNG - [docs.searxng.org](https://docs.searxng.org)
- FreshRSS - [freshrss.github.io](https://freshrss.github.io)
- WhisperX - [whisperX-asr-service no Hugging Face](https://huggingface.co/m-bain/whisperX-asr-service)
- llama.cpp - [ggml-org.github.io](https://ggml-org.github.io)

### Ferramentas de apoio

| Ferramenta | Link |
|------------|------|
| Docker Desktop / Engine | [docker.com](https://www.docker.com/products/docker-desktop) |
| NVIDIA Container Toolkit | [docs.nvidia.com/datacenter/cloud-native/container-toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html) |
| Hugging Face (modelos) | [huggingface.co](https://huggingface.co) |

### Leitura recomendada

- **[Homelab de IA n8n Ollama Qdrant - Diolinux](https://plus.diolinux.com.br/t/construindo-um-homelab-de-ia-n8n-ollama-e-qdrant-para-testes-e-aprendizado/81764)** - Uma das primeiras versões deste tipo de homelab, com configurações detalhadas.
- **[Debian 13 Post-Installation Repository](https://github.com/eddiecsilva/debian-post-install)** - Guia de configuração pós-instalação para Debian 13, incluindo otimizações para desenvolvimento e IA.

---

<a id="licenca"></a>

## 📝 Licença

[MIT](LICENSE) - uso pessoal, educativo e comercial.
