#!/usr/bin/env python3
"""Confere o contrato entre o compose.yaml e um template de ambiente.

A imagem do WhisperX ignorava silenciosamente 24 variaveis com prefixo
WHISPERX_ (e o AnythingLLM ignorava GENERIC_OPENAI_*). Nada quebrava no
compose: a variavel simply nao chegava no container. Este script existe para
que o mesmo tipo de erro nao volte a passar.

Uso: check-env-contract.py [arquivo-de-env]   (padrao: .env.example)
Saida: 0 se tudo bate, 1 se houver problema.
"""

import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
COMPOSE = RAIZ / "compose.yaml"

# Variaveis que o Compose le e que nao precisam existir no template.
IGNORAR = {
    "COMPOSE_PROJECT_NAME",
    "MODELS_DIR",
    "PATH",
    "HOSTNAME",
}

# Segredos: o template so pode ter placeholder vazio.
SEGREDOS = re.compile(
    r"(SECRET|KEY|SALT|PASSWORD|TOKEN)$",
    re.IGNORECASE,
)
VALOR_SUSPEITO = re.compile(r"^[0-9a-f]{32,}$", re.IGNORECASE)


def variaveis_do_compose() -> set:
    texto = COMPOSE.read_text(encoding="utf-8")
    # ${VAR} e ${VAR:-default}
    return set(re.findall(r"\$\{([A-Za-z_][A-Za-z0-9_]*)", texto))


def pares_do_env(caminho: Path) -> list:
    pares = []
    for linha in caminho.read_text(encoding="utf-8").splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#") or "=" not in linha:
            continue
        chave, _, valor = linha.partition("=")
        pares.append((chave.strip(), valor.strip()))
    return pares


def main() -> int:
    caminho = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / ".env.example"
    if not caminho.is_absolute():
        caminho = RAIZ / caminho
    if not caminho.exists():
        print(f"ERRO: {caminho} nao existe")
        return 1

    compose = variaveis_do_compose()
    pares = pares_do_env(caminho)
    env = {chave for chave, _ in pares}
    erros = 0

    faltando = sorted(v for v in compose - env if v not in IGNORAR)
    if faltando:
        erros += 1
        print(f"ERRO [{caminho.name}]: variaveis usadas no compose.yaml e ausentes no template:")
        for nome in faltando:
            print(f"  - {nome}")

    print(f"ok [{caminho.name}]: {len(compose)} variaveis no compose, {len(env)} no template")

    for chave, valor in pares:
        valor = valor.strip().strip('"').strip("'")
        if SEGREDOS.search(chave) and VALOR_SUSPEITO.match(valor):
            erros += 1
            print(f"ERRO [{caminho.name}]: {chave} tem um valor de segredo preenchido")

    if erros:
        print(f"FALHOU [{caminho.name}]: {erros} problema(s)")
        return 1
    print(f"OK [{caminho.name}]: contrato do compose e do template conferido")
    return 0


if __name__ == "__main__":
    sys.exit(main())
