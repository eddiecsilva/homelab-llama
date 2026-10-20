# Changelog

Todas as mudanças relevantes deste projeto.

Formato baseado em [Keep a Changelog](https://keepachangelog.com/pt-BR/1.1.0/) e versionamento semântico.

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
