"""
Núcleo do Agente (Orquestrador Local) com suporte assíncrono ao Ollama,
injeção temporal em tempo real, filtro de personalidade modular e loop
estrito de Tool Calling com limite de tentativas (MAX_TOOL_ITERATIONS = 3).
"""

import inspect
import json
import platform
from typing import Any, Callable, Dict, List, Optional

import ollama
import psutil

from config import settings
from core.persona_filter import PersonaFilter
from tools.code_tools import CODE_TOOLS
from tools.obsidian_tools import OBSIDIAN_TOOLS
from tools.rag_tools import RAG_TOOLS
from tools.sql_tools import SQL_TOOLS
from tools.study_tools import STUDY_TOOLS
from workers.sync_manager import SYNC_TOOLS


# =====================================================================
# FERRAMENTAS BASE DE DIAGNÓSTICO (FASE 1 - TESTE DE TOOL CALLING)
# =====================================================================

def get_hardware_and_runtime_status() -> str:
    """
    Retorna o status atual de memória RAM, CPU, diretórios configurados
    e limites operacionais da máquina local (Avell Storm BS).
    Use esta ferramenta quando o usuário perguntar sobre o status do sistema,
    consumo de memória, caminhos do Vault ou configuração ativa.
    """
    vm = psutil.virtual_memory()
    disk = psutil.disk_usage(str(settings.OBSIDIAN_VAULT_PATH.parent))

    status_payload = {
        "os": f"{platform.system()} {platform.release()}",
        "python_version": platform.python_version(),
        "ram_total_gb": round(vm.total / (1024**3), 2),
        "ram_used_gb": round(vm.used / (1024**3), 2),
        "ram_percent": vm.percent,
        "disk_free_gb": round(disk.free / (1024**3), 2),
        "ollama_model": settings.OLLAMA_REASONING_MODEL,
        "ollama_num_ctx": settings.OLLAMA_NUM_CTX,
        "ollama_keep_alive": settings.OLLAMA_KEEP_ALIVE,
        "obsidian_vault_path": str(settings.OBSIDIAN_VAULT_PATH),
        "persona_file_exists": settings.persona_file_path.exists(),
        "strict_offline_mode": settings.STRICT_OFFLINE_MODE,
        "max_tool_iterations": settings.MAX_TOOL_ITERATIONS,
    }
    return json.dumps(status_payload, ensure_ascii=False, indent=2)


def list_vault_structure() -> str:
    """
    Lista as pastas de primeiro nível e arquivos de configuração dentro
    do Córtex Neural no Obsidian (OBSIDIAN_VAULT_PATH).
    Use esta ferramenta para inspecionar o estado atual do Vault do Obsidian.
    """
    settings.ensure_directories()
    items = []
    for entry in sorted(settings.OBSIDIAN_VAULT_PATH.iterdir()):
        kind = "DIR" if entry.is_dir() else "FILE"
        items.append({"name": entry.name, "type": kind})
    return json.dumps(
        {
            "vault_root": str(settings.OBSIDIAN_VAULT_PATH),
            "entries": items,
        },
        ensure_ascii=False,
        indent=2,
    )


# =====================================================================
# ORQUESTRADOR PRINCIPAL DO AGENTE
# =====================================================================

class LocalHybridAgent:
    """
    Orquestrador central da IA Local Híbrida.
    - Injeta data/hora/dia da semana/fuso em tempo real antes de cada inferência.
    - Aplica `temperature=0.1` na fase de decisão de ferramentas/SQL e `0.6` para respostas criativas/persona.
    - Respeita `num_ctx=4096` e `keep_alive="5m"` para proteger os 6GB de VRAM da RTX 4050.
    - Impõe critério de parada estrito (`MAX_TOOL_ITERATIONS = 3`).
    """

    def __init__(self, tools: Optional[List[Callable[..., Any]]] = None):
        settings.ensure_directories()
        self.client = ollama.AsyncClient(host=settings.OLLAMA_BASE_URL)
        self.persona_filter = PersonaFilter()
        self.history: List[Dict[str, Any]] = []

        # Registro de ferramentas (mapeia nome -> função executável)
        default_tools: List[Callable[..., Any]] = [
            get_hardware_and_runtime_status,
            list_vault_structure,
            *OBSIDIAN_TOOLS,
            *CODE_TOOLS,
            *SQL_TOOLS,
            *RAG_TOOLS,
            *STUDY_TOOLS,
            *SYNC_TOOLS,
        ]
        active_tools = tools if tools is not None else default_tools
        self.tool_registry: Dict[str, Callable[..., Any]] = {
            func.__name__: func for func in active_tools
        }
        self.tool_ables: List[Callable[..., Any]] = active_tools

    def register_tool(self, func: Callable[..., Any]) -> None:
        """Permite acoplar novas ferramentas dinamicamente (Fases 2 e 3)."""
        self.tool_registry[func.__name__] = func
        if func not in self.tool_ables:
            self.tool_ables.append(func)

    def reset_history(self) -> None:
        """Limpa o histórico de conversação em memória."""
        self.history.clear()

    def _build_ollama_options(self, temperature: float) -> Dict[str, Any]:
        """Retorna os parâmetros estritos de hardware para o Ollama."""
        return {
            "num_ctx": settings.OLLAMA_NUM_CTX,
            "temperature": temperature,
        }

    async def _execute_tool_safely(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """
        Executa uma ferramenta registrada de forma isolada (síncrona ou assíncrona),
        capturando exceções para alimentar o loop de auto-correção até o limite máximo.
        """
        if tool_name not in self.tool_registry:
            return {
                "ok": False,
                "error": f"Ferramenta '{tool_name}' não existe. Ferramentas disponíveis: {list(self.tool_registry.keys())}",
            }

        target_func = self.tool_registry[tool_name]
        try:
            if inspect.iscoroutinefunction(target_func):
                result = await target_func(**tool_args)
            else:
                result = target_func(**tool_args)
            return {"ok": True, "output": str(result)}
        except Exception as exc:
            return {
                "ok": False,
                "error": f"Erro ao executar '{tool_name}' com args {tool_args}: {type(exc).__name__}: {exc}",
            }

    async def chat(
        self,
        user_message: str,
        on_tool_event: Optional[Callable[[str, Dict[str, Any], Dict[str, Any], int], None]] = None,
    ) -> str:
        """
        Processa uma mensagem do usuário executando:
        1. Injeção de Percepção Temporal em Tempo Real no System Prompt.
        2. Chamada inicial ao modelo `qwen2.5:7b-instruct-q4_K_M` com `temperature: 0.1` se houver tools.
        3. Loop de Tool Calling com proteção de parada em `MAX_TOOL_ITERATIONS = 3`.
        4. Síntese final com o Filtro de Personalidade Modular (`temperature: 0.6`).
        """
        self.history.append({"role": "user", "content": user_message})

        tool_failures = 0
        iterations = 0
        max_iterations = settings.MAX_TOOL_ITERATIONS

        while iterations < max_iterations:
            # 1. Atualiza o System Prompt com o relógio em tempo real antes de CADA inferência
            system_prompt = self.persona_filter.build_system_prompt(
                mode="tools" if self.tool_ables else "creative"
            )
            messages_payload = [{"role": "system", "content": system_prompt}, *self.history]

            # 2. Inferência com temperature=0.1 para precisão determinística de Tool Calling
            response = await self.client.chat(
                model=settings.OLLAMA_REASONING_MODEL,
                messages=messages_payload,
                tools=self.tool_ables if self.tool_ables else None,
                options=self._build_ollama_options(temperature=settings.OLLAMA_TEMP_TOOLS),
                keep_alive=settings.OLLAMA_KEEP_ALIVE,
            )

            assistant_msg = response.get("message", {})
            tool_calls = assistant_msg.get("tool_calls")

            # Caso o modelo não solicite nenhuma tool:
            if not tool_calls:
                # Se estamos na primeira iteração (conversa aberta/diário/criatividade),
                # caso o conteúdo já tenha sido gerado ou caso queiramos garantir o tom criativo (0.6)
                content = (assistant_msg.get("content") or "").strip()
                if iterations == 0 and not content:
                    # Fallback criativo com temp 0.6
                    creative_prompt = self.persona_filter.build_system_prompt(mode="creative")
                    creative_resp = await self.client.chat(
                        model=settings.OLLAMA_REASONING_MODEL,
                        messages=[{"role": "system", "content": creative_prompt}, *self.history],
                        options=self._build_ollama_options(temperature=settings.OLLAMA_TEMP_CREATIVE),
                        keep_alive=settings.OLLAMA_KEEP_ALIVE,
                    )
                    content = (creative_resp.get("message", {}).get("content") or "").strip()

                self.history.append({"role": "assistant", "content": content})
                return content

            # Registra a intenção de chamada de ferramenta no histórico
            self.history.append(assistant_msg)
            iterations += 1

            # 3. Executa cada tool solicitada pelo LLM
            for call in tool_calls:
                fn_info = call.get("function", {})
                fn_name = fn_info.get("name", "")
                raw_args = fn_info.get("arguments", {})

                if isinstance(raw_args, str):
                    try:
                        fn_args = json.loads(raw_args)
                    except json.JSONDecodeError:
                        fn_args = {}
                else:
                    fn_args = raw_args or {}

                exec_result = await self._execute_tool_safely(fn_name, fn_args)

                if on_tool_event:
                    on_tool_event(fn_name, fn_args, exec_result, iterations)

                if not exec_result["ok"]:
                    tool_failures += 1
                    tool_output_str = json.dumps(
                        {
                            "status": "ERROR",
                            "attempt": iterations,
                            "max_attempts": max_iterations,
                            "details": exec_result["error"],
                        },
                        ensure_ascii=False,
                    )
                else:
                    tool_output_str = exec_result["output"]

                self.history.append(
                    {
                        "role": "tool",
                        "content": tool_output_str,
                    }
                )

            # Critério de Parada Estrito: se atingiu MAX_TOOL_ITERATIONS falhas, interrompe loop
            if tool_failures >= max_iterations:
                break

        # 4. Síntese Final pós-Tools com Filtro de Personalidade e temperature=0.6
        final_system_prompt = self.persona_filter.build_system_prompt(
            mode="creative",
            extra_instructions=(
                "O ciclo de execução de ferramentas foi concluído (ou atingiu o limite máximo de "
                f"{max_iterations} iterações). Sintetize a resposta final para o usuário aplicando "
                "sua personalidade de `/00_Persona/personalidade_principal.md` com fidelidade absoluta "
                "aos dados retornados pelas ferramentas."
            ),
        )
        final_response = await self.client.chat(
            model=settings.OLLAMA_REASONING_MODEL,
            messages=[{"role": "system", "content": final_system_prompt}, *self.history],
            options=self._build_ollama_options(temperature=settings.OLLAMA_TEMP_CREATIVE),
            keep_alive=settings.OLLAMA_KEEP_ALIVE,
        )
        final_text = (final_response.get("message", {}).get("content") or "").strip()
        self.history.append({"role": "assistant", "content": final_text})
        return final_text
