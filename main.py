"""
Ponto de entrada CLI (Fase 1) para testar a IA Local Híbrida via terminal:
- Verifica Injeção Temporal em Tempo Real
- Verifica Filtro de Personalidade Modular (`/00_Persona/personalidade_principal.md`)
- Testa o loop de Tool Calling com Ollama (`qwen2.5:7b-instruct-q4_K_M`)
"""

import argparse
import asyncio
import sys
from typing import Any, Dict

from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.syntax import Syntax

from config import settings
from core.agent_core import LocalHybridAgent
from tools.code_tools import set_code_confirmation_callback

console = Console()


def ask_user_code_diff_confirmation(file_path: str, unified_diff: str) -> bool:
    """Exibe o diff unificado no terminal e solicita confirmação [S/N] antes de alterar código."""
    console.print(
        Panel(
            Syntax(unified_diff, "diff", theme="monokai", line_numbers=False),
            title=f"[bold red]Confirmação de Edição de Código (Search & Replace): {file_path}[/bold red]",
            border_style="red",
        )
    )
    ans = console.input("[bold yellow]Deseja aplicar este diff e criar backup? [S/N]: [/bold yellow]").strip().lower()
    return ans in {"s", "sim", "y", "yes"}


def log_tool_execution(
    tool_name: str, tool_args: Dict[str, Any], result: Dict[str, Any], iteration: int
) -> None:
    status_style = "bold green" if result.get("ok") else "bold red"
    status_label = "SUCESSO" if result.get("ok") else "FALHA"
    console.print(
        Panel(
            f"[bold cyan]Tool:[/bold cyan] {tool_name}\n"
            f"[bold cyan]Args:[/bold cyan] {tool_args}\n"
            f"[bold cyan]Iteração:[/bold cyan] {iteration}/{settings.MAX_TOOL_ITERATIONS}\n"
            f"[{status_style}]Status: {status_label}[/{status_style}]",
            title="[bold yellow]Execução de Ferramenta[/bold yellow]",
            border_style="yellow",
        )
    )


async def run_smoke_test(agent: LocalHybridAgent) -> None:
    """Executa um diagnóstico rápido local da Fase 1 (mesmo sem inferência ou com inferência)."""
    console.print(
        Panel(
            agent.persona_filter.get_realtime_temporal_block(),
            title="[bold green]1. Percepção Temporal em Tempo Real[/bold green]",
            border_style="green",
        )
    )
    persona_preview = agent.persona_filter.load_persona()
    console.print(
        Panel(
            persona_preview,
            title=f"[bold magenta]2. Personalidade Carregada ({settings.persona_file_path})[/bold magenta]",
            border_style="magenta",
        )
    )


async def interactive_cli() -> None:
    parser = argparse.ArgumentParser(description="IA Local Híbrida - CLI de Teste (Fase 1)")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Apenas valida a configuração, injeção temporal e leitura de persona sem chamar o Ollama.",
    )
    parser.add_argument(
        "--prompt",
        type=str,
        default=None,
        help="Envia um único prompt de teste para o agente e encerra.",
    )
    parser.add_argument(
        "--gui",
        action="store_true",
        help="Inicia o Painel de Configurações Desktop (FastAPI em 127.0.0.1:8080 + Webview).",
    )
    args = parser.parse_args()

    if args.gui:
        from gui.desktop_launcher import main as run_gui
        sys.argv = [sys.argv[0]]
        run_gui()
        return

    agent = LocalHybridAgent()

    if args.check:
        await run_smoke_test(agent)
        return

    if args.prompt:
        await run_smoke_test(agent)
        console.print(f"\n[bold blue]Usuário >[/bold blue] {args.prompt}\n")
        try:
            reply = await agent.chat(args.prompt, on_tool_event=log_tool_execution)
            console.print(Panel(Markdown(reply), title="[bold cyan]IA Local Híbrida[/bold cyan]", border_style="cyan"))
        except Exception as exc:
            console.print(
                f"[bold red]Erro ao comunicar com Ollama em {settings.OLLAMA_BASE_URL}:[/bold red] {exc}"
            )
            sys.exit(1)
        return

    # No modo interativo, ativa a confirmação [S/N] para edições fora do Obsidian
    set_code_confirmation_callback(ask_user_code_diff_confirmation)
    await run_smoke_test(agent)
    console.print(
        "[bold cyan]Modo Interativo Iniciado.[/bold cyan] Digite [bold yellow]/sair[/bold yellow] para encerrar "
        "ou [bold yellow]/limpar[/bold yellow] para resetar o histórico.\n"
    )

    while True:
        try:
            user_input = console.input("[bold blue]Você > [/bold blue]").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[dim]Encerrando sessão...[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in {"/sair", "exit", "quit"}:
            break
        if user_input.lower() == "/limpar":
            agent.reset_history()
            console.print("[dim]Histórico de contexto limpo.[/dim]")
            continue

        try:
            reply = await agent.chat(user_input, on_tool_event=log_tool_execution)
            console.print(
                Panel(
                    Markdown(reply),
                    title="[bold cyan]IA Local Híbrida[/bold cyan]",
                    border_style="cyan",
                )
            )
        except Exception as exc:
            console.print(
                f"[bold red]Falha na chamada ao Ollama ({settings.OLLAMA_REASONING_MODEL}):[/bold red] {exc}"
            )


if __name__ == "__main__":
    asyncio.run(interactive_cli())
