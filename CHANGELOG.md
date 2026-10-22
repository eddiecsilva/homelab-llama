# Changelog

Todas as mudanças relevantes deste projeto.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento semântico.

## [1.2.0] - 2026-10-22

Segundo perfil de hardware, para maquinas com 8 GB de VRAM e 16 GB de RAM.

### Perfis de hardware

- `.env.example.small`: template do perfil pequeno (8 GB de VRAM, 16 GB de RAM). Modelo de chat de 8B em Q4_K_M ou menor, contexto 8192, WhisperX `medium` (~2,6 GB de VRAM em vez de 4,2 GB) e limites de RAM apertados.
- `.env.example` continua sendo o perfil padrao (16 GB de VRAM, 32 GB+ de RAM).
- `scripts/check-hardware.py`: preflight que le o `.env`, mede a VRAM e a RAM da maquina, abre o GGUF do `CHAT_MODEL` e diz se o perfil cabe. Aceita `--vram 8 --ram 16` para simular outra maquina.
- README: tabela dos dois perfis, tabela de GGUF por quantizacao (Q6_K, Q5_K_M, Q4_K_M, Q3_K_M) com a VRAM resultante e a regra de escolha. Corrige o "8GB+ VRAM" do texto anterior, que era falso para o modelo de 12B.

### Memoria

- `mem_limit` por servico, driven pelo `.env`: `LLAMA_GPU_MEM_LIMIT`, `LLAMA_EMBED_MEM_LIMIT`, `OPENWEBUI_MEM_LIMIT`, `ANYTHINGLLM_MEM_LIMIT` e `WHISPERX_MEM_LIMIT`.

### CI

- O workflow passa a validar os dois templates de ambiente, nao so o principal.
- `scripts/check-env-contract.py` aceita o arquivo de ambiente como argumento.

## [1.1.0] - 2026-10-22

Corrige o consumo de VRAM do WhisperX, o provider quebrado do AnythingLLM e o
contrato de variaveis de ambiente dos dois servicos. Fecha as issues #1 a #5.

### WhisperX

- O `compose.yaml` passou as 24 variaveis `WHISPERX_*`, que a imagem 0.4.3 nao le. Agora repassa os nomes reais (`DEVICE`, `COMPUTE_TYPE`, `BATCH_SIZE`, `ALIGN_DEVICE`, `CACHE_DIR`, `DEFAULT_MODEL`, `MAX_LOADED_MODELS`, `MAX_FILE_SIZE_MB`, `MODEL_KEEP_ALIVE_SECONDS`, `MODEL_EVICTION_INTERVAL_SECONDS`, `HF_TOKEN`, `LOG_LEVEL`) (issue #1, #4).
- `HF_TOKEN` chega ao container: a diarizacao de falantes (pyannote `community-1`) funciona (issue #2).
- `CACHE_DIR=/app/models`: o modelo de ~3 GB fica no volume e nao e re-baixado a cada recriacao do container (issue #3).
- `BATCH_SIZE` de 16 para 2: 16 janelas de 30 s em paralelo estouravam a VRAM. `ALIGN_DEVICE=cpu` poupa ~1,9 GB de pico (4,2 GB em vez de 7,4 GB).
- `mem_limit` de 8g e healthcheck no servico.

### AnythingLLM

- `GENERIC_OPEN_AI_MAX_TOKENS=4096`: o padrao da imagem (1024) cortava as respostas.
- O provider `generic-openai` passa a receber `GENERIC_OPEN_AI_BASE_PATH`, `GENERIC_OPEN_AI_MODEL_PREF`, `GENERIC_OPEN_AI_API_KEY` e as chaves de embedding com os nomes que a imagem le.

### Open WebUI

- STT (transcricao) apontado para o WhisperX: `AUDIO_STT_ENGINE=openai` e `AUDIO_STT_OPENAI_API_BASE_URL=http://whisperx:9000/v1`. Antes o padrao caia no llama.cpp, que nao tem endpoint de audio.
- `WHISPER_COMPUTE_TYPE=int8`: o container nao tem GPU.
- `CORS_ALLOW_ORIGINS` agora e repassado.

### llama.cpp

- Contexto de 65536 para 16384 (10,3 GB de VRAM em vez de 12,2 GB) para o chat e a transcricao coexistirem na mesma GPU.
- `--sleep-idle-seconds 300`: o servidor libera a VRAM depois de 5 minutos ocioso. A opcao nao tem variavel de ambiente, entao vai na linha de comando do Compose.
- `LLAMA_UBATCH_SIZE=1024` e limiares de compactacao do Open WebUI ajustados (12000/13000) para acompanhar o novo contexto.
- `--fit` segue desligado, agora com o motivo documentado: com contexto e camadas de GPU fixos, o ajuste aborta a inicializacao do servidor.

### SearXNG

- `search.default_lang: "pt-BR"` e `outgoing.request_timeout: 10.0` (3 s e curto para google/bing).
- `SEARXNG_LANGUAGE` removido do Compose: nao e uma variavel do SearXNG.

### FreshRSS

- `CRON_MIN` vem do `.env` (`FRESHRSS_CRON_MIN=30`); antes o cron estava desligado com `0`.

### Infraestrutura

- Healthcheck em todos os 8 servicos, com `depends_on: service_healthy` nas interfaces.
- Rotacao de log por servico (10 MB x 3 arquivos).
- Varredura de variaveis: `SEARXNG_LANGUAGE`, `GENERIC_OPENAI_*` e o bloco TTS do WhisperX (nao lidos pelas imagens) sairam do `.env` e do `compose.yaml`.

### Documentacao

- Secao do WhisperX no README: contrato de variaveis, exemplos de chamada, orcamento de VRAM medido e troubleshooting de `CUDA out of memory` e `cudaErrorInvalidDevice`.

### Limitacoes conhecidas nesta release

- O chat e a transcricao dividem a mesma GPU. Com `large-v3` e um modelo de 12B, 16 GB de VRAM e o piso: use `WHISPERX_MODEL=large-v3-turbo` ou `LLAMA_SLEEP_IDLE_SECONDS` para conviverem.
- O `WHISPERX_LOGLEVEL=INFO` e o padrao agora (antes `ERROR`), para o log mostrar o carregamento do modelo.

### Issues fechadas nesta release

- #1 remover as 24 variaveis de ambiente nao lidas pela imagem do WhisperX
- #2 passar `HF_TOKEN` ao container do WhisperX
- #3 corrigir o volume de cache do WhisperX para `/.cache`
- #4 explicitar `DEVICE`/`COMPUTE_TYPE`/`BATCH_SIZE` e revisar preload contra eviction
- #5 documentar o contrato de variaveis e o setup do WhisperX no README

## [1.0.0] - 2026-10-20

Primeira release estavel do stack. Marca o ambiente completo, com os 8 servicos documentados, rodando local.

### Servicos

| Servico | Imagem | Porta | GPU | Papel |
|---|---|---|---|---|
| `llama-gpu` | `ghcr.io/ggml-org/llama.cpp:server-cuda` | 8085 | sim | Servidor de chat (OpenAI compativel) |
| `llama-embed` | `ghcr.io/ggml-org/llama.cpp:server` | 8086 | nao | Embeddings para RAG |
| `open-webui` | `ghcr.io/open-webui/open-webui:main` | 3000 | nao | Chat, RAG, busca web |
| `anythingllm` | `mintplexlabs/anythingllm:latest` | 3001 | nao | Bases de conhecimento por workspace |
| `vane` | `itzcrazykns1337/vane:slim-latest` | 3002 | nao | Busca web com resposta e citacoes |
| `searxng` | `searxng/searxng:latest` | 8084 | nao | Metabusca privada |
| `freshrss` | `freshrss/freshrss:latest` | 3003 | nao | Leitor de feeds RSS |
| `whisperx` | `learnedmachine/whisperx-asr-service:0.4.3-blackwell` | 9000 | sim | Transcricao com timestamps e diarizacao |

### Modelos

- Chat: `gemma-4-12b-it-Q6_K` (GGUF em `$MODELS_DIR/chat`), contexto 65536, 80 camadas na GPU, `n_parallel=1`.
- Embeddings: `ggml-org/bge-m3-Q8_0-GGUF:Q8_0`, executado em CPU, pooling `cls`, contexto 8192.
- ASR: Whisper `large-v3` + alinhamento wav2vec2 + diarizacao pyannote `community-1`, em CUDA, com `float16` e `BATCH_SIZE=16`.

### Hardware de referencia

- AMD Ryzen 5 5700X (8 nucleos / 16 threads)
- 48 GB RAM
- NVIDIA RTX 5070 Ti 16 GB (CUDA), tag de imagem `-blackwell`
- SSD NVMe 200 GB ou mais
- Debian 13

### Rede e dados

- Rede unica `ai-stack` (bridge). Servicos se falao por nome de container; `host.docker.internal` para o host.
- `BIND_ADDRESS=127.0.0.1`: nada expoe na rede local por padrao.
- Persistencia em `./data/<servico>` e em `$MODELS_DIR` (`chat`, `whisperx`).

### Limitacoes conhecidas

- GPU NVIDIA com NVIDIA Container Toolkit e obrigatoria para `llama-gpu` e `whisperx`.
- O WhisperX nao tem autenticacao: nao exponha a porta 9000 fora da maquina.
- A configuracao do WhisperX ainda carrega variaveis do schema do Space `m-bain/whisperX-asr-service`, que a imagem 0.4.3 nao le. Detalhes e correcoes nas issues #1 a #4.
- O `HF_TOKEN` nao e passado ao container do WhisperX, entao a diarizacao de falantes falha com 403 do Hugging Face (issue #2).
- O volume de cache do WhisperX aponta para `/app/models`, enquanto a imagem cacheia em `/.cache`, entao os modelos sao re-baixados a cada recriacao do container (issue #3).
- Lab planejado para rede local isolada; nao indicado para producao.

### Issues abertas na release

- #1 remover as 24 variaveis de ambiente nao lidas pela imagem do WhisperX
- #2 passar `HF_TOKEN` ao container do WhisperX
- #3 corrigir o volume de cache do WhisperX para `/.cache`
- #4 explicitar `DEVICE`/`COMPUTE_TYPE`/`BATCH_SIZE` e revisar preload contra eviction
- #5 documentar o contrato de variaveis e o setup do WhisperX no README
