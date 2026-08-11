# ForgeGov v3.0.0-M2 Validation Gate

Required local Docker validation:
1. makemigrations --check --dry-run
2. migrate through core.0022
3. manage.py check
4. PriceToWinIntelligenceTests
5. PricingEngineTests regression
6. full core test suite
7. frontend lint
8. TypeScript noEmit
9. production frontend build
10. open an opportunity with stored award history
11. confirm PTW range and comparable evidence
12. confirm PTW warns when evidence is weak
13. confirm margin-at-PTW uses the current M1 cost model
14. record a PTW snapshot and refresh
15. confirm Pursuit Decision surfaces PTW target/confidence/position
