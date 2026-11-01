from pathlib import Path
from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent


class Settings(BaseSettings):
    """Configuração centralizada, portável e tipada da IA Local Híbrida."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Motor Ollama e Limites de Hardware (6GB VRAM Target)
    OLLAMA_BASE_URL: str = Field(default="http://localhost:11434")
    OLLAMA_REASONING_MODEL: str = Field(default="qwen2.5:7b-instruct-q4_K_M")
    OLLAMA_EMBED_MODEL: str = Field(default="nomic-embed-text")
    OLLAMA_NUM_CTX: int = Field(default=4096)
    OLLAMA_TEMP_TOOLS: float = Field(default=0.1)
    OLLAMA_TEMP_CREATIVE: float = Field(default=0.6)
    OLLAMA_KEEP_ALIVE: str = Field(default="5m")

    # Caminhos do Córtex Obsidian, Código e Bancos Locais (relativos à raiz por padrão)
    OBSIDIAN_VAULT_PATH: Path = Field(default=BASE_DIR / "obsidian_vault")
    ALLOWED_CODE_DIRS: str = Field(default=str(BASE_DIR))
    SQLITE_DB_PATH: Path = Field(default=BASE_DIR / "database" / "hybrid_ai.db")
    CHROMA_DB_PATH: Path = Field(default=BASE_DIR / "database" / "chroma_db")

    # Critérios de Parada, Segurança e Temporalidade
    MAX_TOOL_ITERATIONS: int = Field(default=3, ge=1, le=5)
    STRICT_OFFLINE_MODE: bool = Field(default=False)
    TIMEZONE: str = Field(default="America/Sao_Paulo")

    # Servidor GUI Desacoplado (Fase 4)
    GUI_HOST: str = Field(default="127.0.0.1")
    GUI_PORT: int = Field(default=8080)

    @property
    def allowed_code_paths(self) -> List[Path]:
        """Retorna a lista de diretórios de código permitidos resolvidos."""
        return [
            Path(p.strip()).expanduser().resolve()
            for p in self.ALLOWED_CODE_DIRS.split(",")
            if p.strip()
        ]

    @property
    def persona_file_path(self) -> Path:
        """Caminho do arquivo principal de personalidade no Vault do Obsidian."""
        return self.OBSIDIAN_VAULT_PATH / "00_Persona" / "personalidade_principal.md"

    @property
    def skills_dir_path(self) -> Path:
        """Caminho do diretório de Skills dinâmicas no Vault do Obsidian."""
        return self.OBSIDIAN_VAULT_PATH / "01_Skills"

    @property
    def subagents_dir_path(self) -> Path:
        """Caminho do diretório de Sub-Agentes no Vault do Obsidian."""
        return self.OBSIDIAN_VAULT_PATH / "02_Agentes"

    def ensure_directories(self) -> None:
        """Garante que a estrutura base do Vault e do banco exista no disco."""
        self.OBSIDIAN_VAULT_PATH.mkdir(parents=True, exist_ok=True)
        (self.OBSIDIAN_VAULT_PATH / "00_Persona").mkdir(parents=True, exist_ok=True)
        self.skills_dir_path.mkdir(parents=True, exist_ok=True)
        self.subagents_dir_path.mkdir(parents=True, exist_ok=True)
        self.SQLITE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DB_PATH.mkdir(parents=True, exist_ok=True)


settings = Settings()
