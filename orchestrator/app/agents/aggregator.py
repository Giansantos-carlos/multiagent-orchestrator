"""Agrega as respostas parciais dos agentes de domínio em uma resposta final.

Se algum domínio falhou ou está degradado, a resposta final ainda é
retornada com uma nota explícita sobre a indisponibilidade parcial, em vez
de falhar a requisição inteira por causa de um único domínio fora do ar.
"""
from __future__ import annotations


def aggregate(results: dict[str, dict]) -> str:
    parts: list[str] = []
    degraded: list[str] = []

    for domain, result in results.items():
        status = result.get("status")
        answer = result.get("answer", "")
        if status == "ok":
            parts.append(f"[{domain}] {answer}")
        else:
            degraded.append(domain)
            parts.append(f"[{domain} - INDISPONÍVEL] {answer}")

    summary = "\n\n".join(parts) if parts else "Nenhum domínio relevante foi identificado para esta pergunta."
    if degraded:
        summary += f"\n\n(Atenção: resposta parcial — domínios indisponíveis no momento: {', '.join(degraded)}.)"
    return summary
