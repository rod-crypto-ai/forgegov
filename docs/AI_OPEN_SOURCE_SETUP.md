# Open-source ForgeGov AI

ForgeGov supports either the hosted OpenAI Responses API or a self-hosted Ollama model.

## Ollama
Set these values in `.env`:

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:8b
```

Install and start the selected model on the Docker host before using ForgeGov AI.

## Live web research with SearXNG
Run a SearXNG instance with JSON search enabled, then set:

```env
SEARXNG_URL=http://host.docker.internal:8080
AI_WEB_SEARCH_ENABLED=true
```

Without `SEARXNG_URL`, ForgeGov AI still answers from ForgeGov workspace and stored government records, but does not claim to have live web results.
