# Three-Week Project Milestone Plan

Project: Smart Market and Price Decision Support System

Source objectives: `docs/STEVE_NAWAL _DOC.pdf`

Current backend foundation:

- User authentication and profile APIs
- User management APIs
- Administrative areas APIs
- Commodity category and commodity APIs
- Commodity listings APIs
- Orders APIs
- Swagger/OpenAPI and Bruno API documentation

## Milestone Goal

Within three weeks, produce a working prototype that demonstrates the full system flow:

1. Users can register, authenticate, and access features based on role.
2. Market commodities, locations, listings, and prices can be collected and stored.
3. Market data can be imported from at least one external/digital source.
4. Basic analytics and price prediction can be generated from stored data.
5. Market information can be accessed through API endpoints and a USSD-style flow.
6. Reports or dashboard-ready endpoints can support visualization and decision-making.

## Week 1: System Foundation and Market Data Core

Focus: complete the base system and central market database.

Related objectives:

- Objective i: User Management Subsystem
- Objective ii: Market Data Collection Subsystem
- Objective iv: Centralized Market Database Subsystem

### Tasks

- Review and stabilize existing authentication and user management APIs.
- Confirm role permissions for admin, market officer, farmer, entrepreneur, and buyer.
- Finalize the commodity and administrative area models.
- Add or refine market-related models:
  - Market
  - PriceRecord
  - DataSource
  - MarketObservation
- Create APIs for manual market price submission.
- Add validation fields for submitted price data:
  - submitted_by
  - source
  - status
  - verified_by
  - verified_at
- Add filters for price records:
  - commodity
  - area/market
  - date range
  - source
- Update OpenAPI and Bruno collections for the new endpoints.
- Add basic tests for user permissions and price record creation.

### Deliverables

- Working role-based user access.
- Working market price submission API.
- Centralized storage for market prices.
- API documentation for market data endpoints.
- Seed data for areas, commodities, and sample prices.

### Success Criteria

- Admin can manage users, commodities, areas, and markets.
- Market officer can submit and verify market price data.
- Farmers or entrepreneurs can create listings.
- Public or authenticated users can view approved market information based on access rules.

## Week 2: Data Integration, Analytics, and Prediction Prototype

Focus: integrate external data and generate useful market intelligence.

Related objectives:

- Objective iii: Data Scraping and Integration Subsystem
- Objective v: Machine Learning-Based Market Analysis Subsystem
- Objective vi: AI-Based Price Prediction and Recommendation Subsystem

### Tasks

- Select one practical external data source for the prototype.
- Build an import or scraping command for the selected source.
- Normalize imported data into the central price record format.
- Store source metadata:
  - source name
  - source URL or label
  - collection method
  - collected_at
  - confidence level
- Add duplicate detection for imported price records.
- Create analytics endpoints for:
  - average price per commodity
  - price trend by date
  - highest and lowest market price
  - commodity comparison by location
- Prepare a small training dataset from stored price records.
- Build a simple price prediction model using historical prices.
- Start with a practical baseline model:
  - moving average, or
  - linear regression, or
  - random forest regression if the data is enough
- Create a recommendation endpoint that can suggest:
  - best market to sell a commodity
  - expected price movement
  - commodities with better opportunity
- Save generated predictions and recommendations in the database.

### Deliverables

- Data import or scraping command.
- Cleaned imported market data.
- Analytics API endpoints.
- Basic price prediction endpoint.
- Recommendation endpoint.
- Model evaluation notes.

### Success Criteria

- The system can import external market data without breaking existing manual records.
- Analytics endpoints return useful summaries from stored data.
- Price prediction works for at least one commodity.
- Recommendations are explainable using stored prices and trends.

## Week 3: USSD Access, Reports, Testing, and Demonstration

Focus: package the system into a demonstrable final prototype.

Related objectives:

- Objective vii: USSD-Based Market Information Access Subsystem
- Objective viii: Reporting, Visualization, and Decision Support Subsystem

### Tasks

- Design the USSD menu flow:
  - welcome screen
  - select location
  - select commodity
  - view current price
  - view predicted price
  - view recommendation
- Implement a USSD callback endpoint.
- Add a local USSD simulation mode if live gateway integration is not available.
- Create reporting endpoints for:
  - price trend report
  - commodity performance report
  - market comparison report
  - prediction report
- Add export support if time allows:
  - CSV first
  - PDF optional
- Prepare dashboard-ready API responses for charts.
- Run full backend tests.
- Fix endpoint, permission, serializer, and validation issues.
- Update project documentation:
  - README
  - endpoint list
  - setup guide
  - demo credentials
  - API examples
- Prepare final demonstration flow.

### Deliverables

- USSD callback endpoint or simulator.
- Reporting endpoints.
- Dashboard-ready data APIs.
- Updated documentation.
- Tested backend prototype.
- Final demo script.

### Success Criteria

- A user can access commodity price information through USSD-style interaction.
- Reports can show price trends and market comparisons.
- The demo can show the complete path from data collection to prediction and recommendation.
- The system is documented enough for evaluation and presentation.

## Suggested Daily Breakdown

### Week 1

| Day | Work |
| --- | --- |
| Day 1 | Review current backend, confirm models, list missing fields and endpoints. |
| Day 2 | Implement market and price record models. |
| Day 3 | Implement market data collection APIs. |
| Day 4 | Add validation workflow and permissions. |
| Day 5 | Add filters, seed data, and API documentation. |
| Day 6 | Write tests for core market data workflows. |
| Day 7 | Buffer day for fixes and review. |

### Week 2

| Day | Work |
| --- | --- |
| Day 8 | Select data source and define import format. |
| Day 9 | Build scraper or importer. |
| Day 10 | Add data cleaning, normalization, and duplicate detection. |
| Day 11 | Build analytics endpoints. |
| Day 12 | Build baseline prediction model. |
| Day 13 | Build recommendation logic and save results. |
| Day 14 | Test analytics, prediction, and recommendation outputs. |

### Week 3

| Day | Work |
| --- | --- |
| Day 15 | Design and implement USSD menu flow. |
| Day 16 | Connect USSD flow to market price and prediction data. |
| Day 17 | Build reporting endpoints. |
| Day 18 | Prepare dashboard-ready chart responses. |
| Day 19 | Full testing and bug fixing. |
| Day 20 | Documentation and demo preparation. |
| Day 21 | Final review, cleanup, and presentation rehearsal. |

## Minimum Viable Prototype Scope

If time becomes limited, prioritize this smaller but complete scope:

1. Authentication and role-based access.
2. Commodities, areas, markets, and price records.
3. Manual price collection by market officer.
4. One data import source.
5. Basic price trend analytics.
6. Simple price prediction for one or two commodities.
7. USSD simulator for price lookup.
8. One report endpoint for dashboard visualization.

## Recommended Backend Apps

Existing apps to continue using:

- `apps/auth`
- `apps/users`
- `apps/areas`
- `apps/commodities`
- `apps/listings`
- `apps/orders`

Recommended new apps:

- `apps/markets`
- `apps/market_data`
- `apps/integrations`
- `apps/analytics`
- `apps/predictions`
- `apps/recommendations`
- `apps/ussd`
- `apps/reports`

## Evaluation Mapping

| Objective | Evidence to Show |
| --- | --- |
| User Management | Registration, login, roles, permissions, user admin APIs |
| Market Data Collection | Manual price submission and verification |
| Data Scraping and Integration | Import/scraper command and stored external data |
| Centralized Market Database | PostgreSQL tables for commodities, markets, prices, sources, predictions |
| ML Market Analysis | Trend, demand, and comparison analytics |
| AI Price Prediction | Prediction endpoint and model output |
| USSD Access | USSD callback or simulator flow |
| Reporting and Decision Support | Reports, dashboard-ready APIs, recommendations |

## Main Risks and Controls

| Risk | Control |
| --- | --- |
| Too many modules for three weeks | Build a complete thin slice first, then improve each part. |
| Not enough real data for ML | Use seeded historical data and clearly document it as prototype data. |
| Scraping source changes or blocks access | Support CSV/manual import as a fallback integration source. |
| USSD gateway setup delays | Build a local simulator and keep live Africa's Talking integration optional. |
| Reports take too much time | Start with JSON chart endpoints before CSV/PDF exports. |

## Final Demo Flow

1. Admin logs in.
2. Admin creates or reviews users, commodities, areas, and markets.
3. Market officer submits commodity price data.
4. System imports extra data from an external source.
5. Analytics endpoint shows price trends.
6. Prediction endpoint forecasts a commodity price.
7. Recommendation endpoint suggests a selling opportunity.
8. USSD flow retrieves price information for a basic phone user.
9. Reporting endpoint provides dashboard-ready decision support data.
