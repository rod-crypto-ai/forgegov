# ForgeGov v3.0.0-M4 Validation Gate

Required local Docker validation:
1. makemigrations --check --dry-run
2. migrate through core.0024
3. manage.py check
4. PortfolioIntelligenceTests
5. PrimeSubCashFlowTests regression
6. PriceToWinIntelligenceTests regression
7. PricingEngineTests regression
8. full core test suite
9. frontend lint
10. TypeScript noEmit
11. production frontend build
12. Reports → Executive Portfolio loads
13. weighted pipeline matches stored probability assumptions
14. pricing changes flow into profit/margin
15. working-capital changes flow into portfolio liquidity
16. agency concentration generates risk when material
17. Record Executive Snapshot persists history
