# ForgeGov v3.0.0-M3 Validation Gate

Required local Docker validation:
1. makemigrations --check --dry-run
2. migrate through core.0023
3. manage.py check
4. PrimeSubCashFlowTests
5. PriceToWinIntelligenceTests regression
6. PricingEngineTests regression
7. full core test suite
8. frontend lint
9. TypeScript noEmit
10. production frontend build
11. add subcontractor and validate contribution math
12. enter payment timing and capital assumptions
13. verify cash-flow risk changes with available capital
14. create a new pricing revision and confirm M3 assumptions persist
15. verify Pursuit Decision surfaces working-capital risk
