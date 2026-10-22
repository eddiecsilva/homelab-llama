#!/usr/bin/env python3
"""Confere o contrato entre o compose.yaml e o .env.example.

A imagem do WhisperX ignorava silenciosamente 24 variaveis com prefixo
WHISPERX_ (e o AnythingLLM ignorava GENERIC_OPENAI_*). Nada quebrava no
compose: a variavel simply nao chegava no container. Este script existe para
que o mesmo tipo de erro nao volte a passar.

Saida: 0 se tudo bate, 1 se houver problema.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = RAIZ / "compose.yaml"
ENV_EXAMPLE = RAIZ / ".env.example"

# Variaveis que o Compose le e que nao precisam existir no .env.example.
IGNORAR = {
    "COMPOSE_PROJECT_NAME",
    "MODELS_DIR",
    "PATH",
    "HOSTNAME",
}

# Segredos: o .env.example so pode ter placeholder vazio.
SEGREDOS = re.compile(
    r"(SECRET|KEY|SALT|PASSWORD|TOKEN)$",
    re.IGNORECASE,
)
VALOR_SUSPEITO = re.compile(r"^[0-9a-f]{32,}$", re.IGNORECASE)


def variaveis_do_compose() -> set:
    texto = COMPOSE.read_text(encoding="utf-8")
    # ${VAR} e ${VAR:-default}
    return set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", texto))


def variaveis_do_env() -> set:
    chaves = set()
    for linha in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chaves.add(linha.split("=", 1)[0].strip())
    return chaves


def main() -> int:
    compose = variaveis_do_compose()
    env = variaveis_do_env()
    erros = 0

    faltando = sorted(v for v in compose - env if v not in IGNORAR)
    if faltando:
        erros += 1
        print("ERRO: variaveis usadas no compose.yaml e ausentes no .env.example:")
        for nome in faltando:
            print(f"  - {nome}")

    print(f"ok: {len(compose)} variaveis no compose, {len(env)} no .env.example")

    # Segredos com valor real no .env.example
    for linha in ENV_EXAMPLE.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if SEGREDOS.search(chave) and VALOR_SUSPEITO.match(valor):
            erros += 1
            print(f"ERRO: {chave} tem um valor de segredo preenchido no .env.example")

    if erros:
        print(f"FALHOU: {erros} problema(s)")
        return 1
    print("OK: contrato do compose e do .env.example conferido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
