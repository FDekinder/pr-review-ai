"""
Configuration for the PR Review AI system.

WHY a dedicated config file?
Instead of scattering configuration values across files, we centralize them here.
This makes it easy to:
  1. Change settings without hunting through code
  2. Use environment variables for secrets (like GitHub tokens)
  3. Have different configs for development vs production
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    Pydantic's BaseSettings automatically reads from:
    1. Constructor arguments
    2. Environment variables
    3. .env file (if python-dotenv is installed)

    This means you can override any setting by setting an environment variable.
    Example: set OLLAMA_BASE_URL=http://other-host:11434
    """

    # Ollama Configuration
    # This is the default URL where Ollama listens after installation
    ollama_base_url: str = "http://localhost:11434"

    # Model assignments - which model each agent uses
    # Smaller models (3B) = faster but less capable
    # Larger models (7B+) = slower but better reasoning
    fast_model: str = "llama3.2:3b"           # For simple tasks: triage, standards
    balanced_model: str = "qwen2.5-coder:7b"  # For code analysis: security, performance
    deep_model: str = "deepseek-coder-v2:16b" # For complex analysis (Week 4)

    # GitHub Configuration
    github_token: str = ""  # Set via GITHUB_TOKEN environment variable

    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Database (Week 4)
    database_url: str = "sqlite:///./pr_reviews.db"  # SQLite for now, Postgres later

    # Agent Configuration
    max_agent_timeout: int = 120  # seconds - max time an agent can take
    max_concurrent_agents: int = 3  # how many agents run in parallel

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
    }


# Singleton instance - import this everywhere
settings = Settings()
