# Open-source ForgeGov AI

ForgeGov can use a self-hosted Ollama model as its primary reasoning engine while continuing to retrieve current web results from the bundled SearXNG service.

## 1. Install and start Ollama

Install Ollama on the Docker host, start it, and pull a model. The default ForgeGov model setting is `qwen3:8b`:

```bash
ollama pull qwen3:8b
```

## 2. Enable open-source mode

From the ForgeGov project folder, run:

```bash
./scripts/enable_open_source_ai.sh
```

To choose another installed Ollama model:

```bash
./scripts/enable_open_source_ai.sh "your-model-name"
```

The script sets:

```env
AI_PROVIDER=ollama
OLLAMA_BASE_URL=http://host.docker.internal:11434
OLLAMA_MODEL=qwen3:8b
```

It then recreates the backend and confirms that Ollama is reachable and the selected model is installed.

## 3. Enable live web research

```bash
./scripts/enable_live_web.sh
```

This sets:

```env
SEARXNG_URL=http://searxng:8080
AI_WEB_SEARCH_ENABLED=true
```

ForgeGov AI combines the selected model with organization-scoped ForgeGov records, government opportunity data, and live SearXNG results. Answers identify sources and separate verified facts from analysis and recommendations.

## Hosted OpenAI fallback

OpenAI remains supported as an optional provider. To switch back, set:

```env
AI_PROVIDER=openai
OPENAI_API_KEY=<server-side key>
```

Then recreate the backend:

```bash
docker compose up -d --force-recreate backend
```
