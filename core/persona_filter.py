"""
Filtro Modular de Personalidade e Percepção Temporal em Tempo Real.
Carrega a identidade da IA a partir de `/00_Persona/personalidade_principal.md`
e injeta metadados temporais exatos antes de cada inferência, mantendo a camada
de execução de ferramentas determinística e isolada.
"""

from datetime import datetime
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from config import settings

DIAS_SEMANA_PT = {
    0: "Segunda-feira",
    1: "Terça-feira",
    2: "Quarta-feira",
    3: "Quinta-feira",
    4: "Sexta-feira",
    5: "Sábado",
    6: "Domingo",
}

DEFAULT_PERSONA_FALLBACK = (
    "Você é uma IA Local Híbrida Soberana operando em arquitetura Offline-First. "
    "Responda com clareza técnica, precisão e em português brasileiro."
)


class PersonaFilter:
    """Gerencia o carregamento dinâmico da persona no Obsidian e a injeção temporal."""

    def __init__(self, persona_path: Optional[Path] = None, timezone_str: Optional[str] = None):
        self.persona_path: Path = persona_path or settings.persona_file_path
        self.timezone_str: str = timezone_str or settings.TIMEZONE
        self._cached_content: str = DEFAULT_PERSONA_FALLBACK
        self._last_mtime: float = 0.0

    def load_persona(self, force_reload: bool = False) -> str:
        """
        Lê `/00_Persona/personalidade_principal.md` com cache baseado em mtime.
        Se o arquivo for editado no Obsidian, recarrega automaticamente na próxima inferência.
        """
        try:
            if not self.persona_path.exists():
                return DEFAULT_PERSONA_FALLBACK

            current_mtime = self.persona_path.stat().st_mtime
            if force_reload or current_mtime > self._last_mtime:
                raw_text = self.persona_path.read_text(encoding="utf-8").strip()
                if raw_text:
                    self._cached_content = raw_text
                    self._last_mtime = current_mtime
        except Exception as exc:
            # Em caso de falha de I/O, mantém o último estado válido sem quebrar as tools
            return f"{self._cached_content}\n\n[Aviso interno: falha ao ler persona: {exc}]"

        return self._cached_content

    def get_realtime_temporal_block(self) -> str:
        """
        Gera o bloco estrito de Percepção Temporal em Tempo Real com data,
        hora exata, dia da semana e fuso horário.
        """
        try:
            tz = ZoneInfo(self.timezone_str)
        except Exception:
            tz = ZoneInfo("UTC")

        now = datetime.now(tz)
        dia_semana = DIAS_SEMANA_PT.get(now.weekday(), "Desconhecido")
        offset_str = now.strftime("%z")
        if len(offset_str) == 5:
            offset_str = f"{offset_str[:3]}:{offset_str[3:]}"

        return (
            "=== PERCEPÇÃO TEMPORAL EM TEMPO REAL ===\n"
            f"- Data Atual: {now.strftime('%Y-%m-%d')} ({now.strftime('%d/%m/%Y')})\n"
            f"- Hora Exata: {now.strftime('%H:%M:%S')}\n"
            f"- Dia da Semana: {dia_semana}\n"
            f"- Fuso Horário: {self.timezone_str} (UTC{offset_str})\n"
            f"- Timestamp ISO-8601: {now.isoformat()}\n"
            "========================================"
        )

    def build_system_prompt(self, mode: str = "creative", extra_instructions: Optional[str] = None) -> str:
        """
        Constrói o System Prompt completo combinando:
        1. Percepção Temporal em Tempo Real (sempre atualizada no instante da chamada)
        2. Regras operacionais determinísticas (Tool Calling / Zero Alucinação)
        3. Camada de Personalidade isolada (aplicada na síntese/resposta ao usuário)
        """
        temporal_block = self.get_realtime_temporal_block()
        persona_content = self.load_persona()

        operational_rules = (
            "=== REGRAS DE ENGENHARIA E EXECUÇÃO ===\n"
            "1. Quando precisar executar uma ferramenta (tool), forneça argumentos JSON estritos e exatos, "
            "sem inventar parâmetros e sem deixar o estilo da persona alterar nomes de campos ou queries.\n"
            "2. ZERO ALUCINAÇÃO MATEMÁTICA: Nunca faça contagens ou agregações de dados de cabeça; "
            "utilize ferramentas determinísticas quando disponíveis.\n"
            f"3. Modo Estritamente Offline Ativo: {'SIM' if settings.STRICT_OFFLINE_MODE else 'NÃO'}.\n"
            "======================================="
        )

        parts = [temporal_block, operational_rules]

        if mode == "tools":
            # Na fase de seleção/recuperação de tool, a persona entra como contexto de identidade,
            # mas com instrução explícita de priorizar precisão sintática nas chamadas de função.
            parts.append(
                "=== FILTRO DE PERSONALIDADE (MODO DETERMINÍSTICO DE TOOLS) ===\n"
                "Mantenha sua identidade abaixo ao responder ao usuário final, mas durante chamadas "
                "de ferramentas (tool_calls) opere com precisão puramente técnica:\n\n"
                f"{persona_content}"
            )
        else:
            parts.append(
                "=== IDENTIDADE E PERSONALIDADE ATIVA (/00_Persona/personalidade_principal.md) ===\n"
                f"{persona_content}"
            )

        if extra_instructions:
            parts.append(f"=== CONTEXTO ADICIONAL ===\n{extra_instructions}")

        return "\n\n".join(parts)
