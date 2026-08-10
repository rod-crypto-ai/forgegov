# ForgeGov v3.0.0-M1 Validation Gate

Static source validation is included in the release package. Local Docker remains the release gate.

Required:
1. makemigrations --check --dry-run
2. migrate
3. manage.py check
4. PricingEngineTests
5. full core test suite
6. frontend lint
7. TypeScript noEmit
8. production frontend build
9. browser test Pricing workspace
10. verify pricing numbers persist after refresh
11. create pricing revision and confirm prior revision stays locked
12. verify Pursuit Decision displays pricing economics
13. regression-test M5.2 Overview-first navigation and compact dashboard
