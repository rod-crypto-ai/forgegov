# ForgeGov MVP

A working Python/Streamlit foundation for government opportunity discovery, award intelligence, incumbent analysis, saved searches, and capture pipeline management.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# add your SAM.gov API key to .env
streamlit run app.py
```

## Implemented
- Live SAM.gov opportunity search
- Live USASpending award search
- SQLite persistence
- Saved searches
- Opportunity detail and related-award analysis
- Incumbent-likelihood heuristic with confidence notes
- Persistent capture pipeline with stages, notes, value, probability, and due dates
- Dashboard metrics and deadline view
- CSV exports

## Not falsely represented as complete
Authentication, multi-user permissions, email/Slack alerts, document RAG, local Ollama analysis, SLED feeds, and production deployment are next phases.
