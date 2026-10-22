#!/usr/bin/env python3
"""Preflight de hardware: este .env roda nesta maquina?

Compara o que o .env pede (modelo de chat, contexto, modelo do WhisperX) com o
que a maquina tem (VRAM da GPU, RAM) e diz o que ajustar.

Os numeros de VRAM sao estimativas calibradas nas medicoes do homelab
(RTX 5070 Ti 16 GB, llama.cpp 0.7, whisperx 0.4.3):
  - pesos do GGUF ocupam quase o tamanho do arquivo
  - KV cache (q8_0): ~1,8 KB por token por bilhao de parametros
  - buffer de computacao: ~0,2 GB + 0,15 GB por 1024 de ubatch
  - WhisperX: pesos do modelo + 0,6 GB + 0,25 GB por janela de batch
    (alinhamento na GPU soma ~2 GB; na CPU, 0 GB de VRAM e ~2 GB de RAM)

Uso:
  python3 scripts/check-hardware.py [--env .env] [--vram 8] [--ram 16]
Saida: 0 se o perfil couber, 1 se nao couber.
"""

import argparse
import os
import re
import struct
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

# Pesos em fp16 (GB) por modelo do WhisperX.
WHISPERX_PESOS = {
    "large-v3": 3.09,
    "large": 3.09,
    "large-v3-turbo": 1.62,
    "turbo": 1.62,
    "medium": 1.54,
    "small": 0.48,
    "base": 0.14,
    "tiny": 0.08,
}

RAM_CONTAINERS = 1.7      # open-webui + anythingllm + vane + searxng + freshrss + llama-embed
RAM_WHISPERX_BASE = 1.5   # processo, VAD e buffers
RAM_ALIGN_CPU = 2.0       # wav2vec2 de alinhamento na CPU
RAM_OS_HEADLESS = 1.5
RAM_OS_DESKTOP = 3.5


# ---------------------------------------------------------------- GGUF
def ler_metadados_gguf(caminho: Path) -> dict:
    """Le os metadados uteis do cabecalho do GGUF."""
    dados = {}
    try:
        with caminho.open("rb") as f:
            if f.read(4) != b"GGUF":
                return dados
            f.read(4)                      # versao
            f.read(8)                      # tensor_count
            kv_count = struct.unpack("<Q", f.read(8))[0]
            for _ in range(kv_count):
                chave = _ler_string(f)
                tipo = struct.unpack("<I", f.read(4))[0]
                valor = _ler_valor(f, tipo)
                if chave in ("general.size_label", "general.parameter_count",
                             "general.file_type", "general.name"):
                    dados[chave] = valor
    except Exception:
        return dados
    return dados


def parametros_em_bilhoes(metadados: dict, pesos_gb: float) -> float:
    """Numero de parametros do modelo, em bilhoes."""
    if "general.parameter_count" in metadados:
        return float(metadados["general.parameter_count"]) / 1e9
    rotulo = str(metadados.get("general.size_label", ""))
    achado = re.search(r"([\d.]+)\s*([BbMm])", rotulo)
    if achado:
        numero = float(achado.group(1))
        return numero if achado.group(2).lower() == "b" else numero / 1000
    # Sem rotulo: estima assumindo Q6_K (6,5 bits por parametro)
    return pesos_gb * 1024**3 * 8 / 6.5 / 1e9


def _ler_string(f) -> str:
    tamanho = struct.unpack("<Q", f.read(8))[0]
    return f.read(tamanho).decode("utf-8", "replace")


def _ler_valor(f, tipo: int):
    if tipo == 0:
        return struct.unpack("<B", f.read(1))[0]
    if tipo == 1:
        return struct.unpack("<b", f.read(1))[0]
    if tipo == 2:
        return struct.unpack("<H", f.read(2))[0]
    if tipo == 3:
        return struct.unpack("<h", f.read(2))[0]
    if tipo == 4:
        return struct.unpack("<I", f.read(4))[0]
    if tipo == 5:
        return struct.unpack("<i", f.read(4))[0]
    if tipo == 6:
        return struct.unpack("<f", f.read(4))[0]
    if tipo == 7:
        return bool(struct.unpack("<B", f.read(1))[0])
    if tipo == 8:
        return _ler_string(f)
    if tipo == 9:
        sub_tipo = struct.unpack("<I", f.read(4))[0]
        n = struct.unpack("<Q", f.read(8))[0]
        return [_ler_valor(f, sub_tipo) for _ in range(min(n, 0))] or None
    if tipo == 10:
        return struct.unpack("<Q", f.read(8))[0]
    if tipo == 11:
        return struct.unpack("<q", f.read(8))[0]
    if tipo == 12:
        return struct.unpack("<d", f.read(8))[0]
    raise ValueError(f"tipo GGUF desconhecido: {tipo}")


# ---------------------------------------------------------------- maquina
def ler_env(caminho: Path) -> dict:
    valores = {}
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        valores[chave.strip()] = valor.strip().strip('"').strip("'")
    return valores


def vram_da_gpu() -> float:
    try:
        saida = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=10, check=True,
        ).stdout
        return float(saida.strip().splitlines()[0]) / 1024
    except Exception:
        return 0.0


def ram_da_maquina() -> float:
    try:
        for linha in Path("/proc/meminfo").read_text().splitlines():
            if linha.startswith("MemTotal:"):
                return int(linha.split()[1]) / 1024 / 1024
    except Exception:
        pass
    return 0.0


def achar_gguf(diretorio: Path, nome: str):
    if not nome or not diretorio.exists():
        return None
    alvo = nome.lower()
    for caminho in sorted(diretorio.rglob("*.gguf")):
        if alvo in caminho.name.lower():
            return caminho
    return None


# ---------------------------------------------------------------- estimativas
def vram_do_chat(pesos_gb: float, params_b: float, ctx: int, ubatch: int) -> float:
    """Pesos + buffer de computacao + KV cache (q8_0)."""
    compute_gb = 0.7 + 0.5 * (ubatch / 1024)
    kv_gb = ctx * params_b * 1e-6
    return pesos_gb + compute_gb + kv_gb


def vram_do_whisperx(modelo: str, batch: int, align: str) -> float:
    pesos = WHISPERX_PESOS.get(modelo, 3.09)
    total = pesos + 0.6 + 0.25 * batch
    if align == "cuda":
        total += 2.0
    return total


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--env", default=".env", help="arquivo de ambiente (padrao: .env)")
    ap.add_argument("--vram", type=float, help="forca a VRAM em GB (para simular outra maquina)")
    ap.add_argument("--ram", type=float, help="forca a RAM em GB (para simular outra maquina)")
    args = ap.parse_args()

    caminho = Path(args.env)
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    if not caminho.exists():
        for alternativa in (".env.example.small", ".env.example"):
            if (RAIZ / alternativa).exists():
                caminho = RAIZ / alternativa
                break
    if not caminho.exists():
        print("ERRO: nenhum arquivo de ambiente encontrado")
        return 1

    env = ler_env(caminho)
    print(f"perfil: {caminho.name}\n")

    # -- modelo de chat
    modelos_dir = Path(env.get("MODELS_DIR", "./models")) / "chat"
    if not modelos_dir.is_absolute():
        modelos_dir = RAIZ / modelos_dir
    chat_model = env.get("CHAT_MODEL", "")
    ctx = int(env.get("LLAMA_CTX_SIZE", "8192"))
    ubatch = int(env.get("LLAMA_UBATCH_SIZE", "1024"))

    gguf = achar_gguf(modelos_dir, chat_model)
    pesos = params_b = 0.0
    if gguf:
        pesos = gguf.stat().st_size / 1024**3
        metadados = ler_metadados_gguf(gguf)
        params_b = parametros_em_bilhoes(metadados, pesos)
        print(f"modelo de chat : {gguf.name}")
        print(f"                {pesos:.2f} GB no disco, ~{params_b:.1f}B parametros"
              f" ({metadados.get('general.size_label', 'estimado')})")
    else:
        print(f"modelo de chat : {chat_model or '(nao definido)'} - arquivo nao encontrado em {modelos_dir}")
        print(f"                (a pasta models/ esta no .gitignore; baixe o GGUF antes)")

    vram_chat = vram_do_chat(pesos, params_b, ctx, ubatch) if pesos else 0.0

    # -- whisperx
    wx_model = env.get("WHISPERX_MODEL", "large-v3")
    wx_batch = int(env.get("WHISPERX_BATCH_SIZE", "2"))
    wx_align = env.get("WHISPERX_ALIGN_DEVICE", "cpu")
    vram_wx = vram_do_whisperx(wx_model, wx_batch, wx_align)

    # -- maquina
    vram_total = args.vram or vram_da_gpu()
    ram_total = args.ram or ram_da_maquina()
    vram_livre = vram_total - 1.0 if vram_total else 0.0  # ~1 GB do desktop

    print(f"\nestimativa de VRAM")
    if vram_chat:
        print(f"  llama-gpu    {vram_chat:5.2f} GB  (ctx {ctx}, ubatch {ubatch})")
    print(f"  whisperx     {vram_wx:5.2f} GB  ({wx_model}, batch {wx_batch}, align {wx_align})")
    if vram_chat:
        print(f"  simultaneo   {vram_chat + vram_wx:5.2f} GB")
    print(f"  disponivel   {vram_livre:5.2f} GB  de {vram_total:.0f} GB de VRAM"
          + ("  [desktop ~1 GB descontado]" if not args.vram else "  [simulado]"))

    # -- RAM
    ram_containers = RAM_CONTAINERS + RAM_WHISPERX_BASE + (RAM_ALIGN_CPU if wx_align == "cpu" else 0)
    print(f"\nestimativa de RAM")
    print(f"  containers   {ram_containers:5.2f} GB")
    print(f"  maquina      {ram_total:5.2f} GB" + ("  [simulado]" if args.ram else ""))

    # -- veredito
    problemas = []
    if vram_total:
        if vram_chat and vram_chat > vram_livre:
            problemas.append(
                f"o modelo de chat precisa de {vram_chat:.1f} GB de VRAM e a maquina tem "
                f"{vram_livre:.1f} GB  ->  use um GGUF menor (Q4_K_M ou Q3_K_M) "
                f"ou reduza LLAMA_CTX_SIZE")
        if vram_chat and vram_wx and vram_chat + vram_wx > vram_livre:
            problemas.append(
                f"chat e transcricao juntos precisam de {vram_chat + vram_wx:.1f} GB  ->  "
                f"o chat vai dormir (LLAMA_SLEEP_IDLE_SECONDS) ou use um WhisperX menor "
                f"(medium ~{vram_do_whisperx('medium', wx_batch, 'cpu'):.1f} GB, "
                f"large-v3-turbo ~{vram_do_whisperx('large-v3-turbo', wx_batch, 'cpu'):.1f} GB)")
    if ram_total and ram_containers + RAM_OS_HEADLESS > ram_total:
        problemas.append(
            f"a stack precisa de ~{ram_containers + RAM_OS_HEADLESS:.1f} GB de RAM (headless) "
            f"e a maquina tem {ram_total:.0f} GB  ->  feche o WhisperX quando nao usar, "
            f"ou reduza os limites de RAM")

    print()
    if problemas:
        for p in problemas:
            print(f"ATENCAO: {p}")
        return 1
    print("OK: o perfil deste .env cabe nesta maquina")
    return 0


if __name__ == "__main__":
    sys.exit(main())
