# Brad's Cannibalization Diagrams

This document provides visual companion artifacts for:

- `docs/brad_cannibalization_plan.md`
- `docs/brad_cannibalization_plan_aevah.md`
- `docs/brad_cannibalization_implementation_blueprint.md`

The diagrams are written in Mermaid so they can render in many IDEs and documentation viewers.

## 1. End-to-end flowchart

```mermaid
flowchart TD
    A[Raw SPINS POS Data] --> B[Ingest Into Aevah]
    B --> C[Governed Semantic Layer]
    C --> D[Curated Weekly Panel<br/>UPC x Geography x Week]
    D --> E[Competitive Set Definitions]
    D --> F[Historical Event Views<br/>Launch Promo Distribution]
    E --> G[Feature Views]
    F --> G
    G --> H[Target Definition]
    H --> I[Baseline Model Training]
    G --> I
    I --> J[Validation Across Time and Markets]
    J --> K[Prediction Outputs]
    K --> L[Explainability Outputs]
    K --> M[Scenario Planning Outputs]
    L --> N[Dashboards and Executive Views]
    M --> N
    L --> O[Agent-Ready Intelligence]
    M --> O
    K --> P[Monitoring and Retraining]
    L --> P
```

## 2. Delivery sequence through Aevah

```mermaid
sequenceDiagram
    participant S as SPINS Source Data
    participant A as Aevah Ingestion
    participant G as Governed Semantic Layer
    participant F as Feature Pipeline
    participant M as ML Modeling Layer
    participant X as Explainability Layer
    participant D as Dashboards / Agents

    S->>A: Deliver raw POS extracts
    A->>G: Standardize keys and business entities
    G->>G: Apply governance lineage and semantic definitions
    G->>F: Publish curated weekly panel
    F->>F: Build own-item competitor and market features
    F->>M: Send feature-ready training data
    M->>M: Train and validate cannibalization models
    M->>X: Publish predictions and driver outputs
    X->>D: Expose business-ready insights
    D-->>M: Capture usage feedback and business review
    M->>F: Request updated features as logic evolves
    M->>D: Publish refreshed scores on scoring cadence
```

## 3. Modeling decision flow

```mermaid
flowchart TD
    A[Start Modeling Design] --> B{What business problem is primary?}
    B -->|Launch impact| C[Prioritize launch event labels]
    B -->|Promo impact| D[Prioritize promo event labels]
    B -->|Assortment impact| E[Prioritize assortment change labels]
    B -->|General demand transfer| F[Prioritize ongoing substitution labels]

    C --> G{What target best fits?}
    D --> G
    E --> G
    F --> G

    G -->|Underlying demand| H[Use Base Units first]
    G -->|Observed operational demand| I[Use Units first]
    G -->|Financial prioritization| J[Add Dollars and Margin views]

    H --> K[Create competitive-set features]
    I --> K
    J --> K

    K --> L{Need explainable baseline first?}
    L -->|Yes| M[Regression + Gradient Boosting + Panel Models]
    L -->|No but usually still yes| M

    M --> N[Validate on future weeks and holdout markets]
    N --> O{Performance and business trust acceptable?}
    O -->|Yes| P[Deploy and operationalize]
    O -->|No| Q[Refine targets features and competitive sets]
    Q --> K
```

## 4. Data-to-feature flow

```mermaid
flowchart LR
    A[Raw POS Fields] --> B[Curated Facts]
    B --> C1[Demand Measures]
    B --> C2[Price Measures]
    B --> C3[Promo Measures]
    B --> C4[Distribution Measures]
    B --> C5[Product Attributes]
    B --> C6[Market Context]

    C1 --> D[Own-Item Features]
    C2 --> D
    C3 --> D
    C4 --> D

    C2 --> E[Competitive Features]
    C3 --> E
    C4 --> E
    C5 --> E

    C5 --> F[Similarity Features]
    C6 --> G[Seasonality and Market Features]

    D --> H[Model Feature Store / View]
    E --> H
    F --> H
    G --> H
```

## 5. Historical measurement flow

```mermaid
flowchart TD
    A[Curated Weekly Panel] --> B[Identify Events]
    B --> C1[Launch Events]
    B --> C2[Promo Events]
    B --> C3[Distribution Gain Events]
    B --> C4[Assortment Change Events]

    C1 --> D[Measure Impact on Incumbent SKUs]
    C2 --> D
    C3 --> D
    C4 --> D

    D --> E[Estimate Historical Demand Transfer]
    E --> F[Validate Competitive Set Logic]
    E --> G[Create Training Labels]
```

## 6. Business consumption flow

```mermaid
flowchart TD
    A[Predictions] --> B[SKU Risk View]
    A --> C[Donor Recipient View]
    A --> D[Market Risk View]
    A --> E[Scenario Planning View]

    B --> F[Category and Brand Teams]
    C --> F
    D --> G[Sales and Commercial Planning]
    E --> H[Launch and Assortment Decisions]

    A --> I[Agent-Ready Output Tables]
    I --> J[Aevah Agents Answer Business Questions]
```

## 7. Operational monitoring sequence

```mermaid
sequenceDiagram
    participant P as Production Scoring
    participant O as Output Monitoring
    participant R as Retraining Process
    participant G as Governance / Lineage
    participant U as Business Users

    P->>O: Publish predictions and features
    O->>O: Check drift quality and stability
    O->>G: Log versions lineage and audit metadata
    U-->>O: Report anomalies or trust issues
    O->>R: Trigger review when thresholds are exceeded
    R->>G: Register new model and feature versions
    R->>P: Deploy refreshed model
    P->>U: Publish updated outputs
```

## 8. Suggested team swimlane view

```mermaid
flowchart LR
    subgraph DE[Data Engineering / Platform]
        A1[Ingest Data]
        A2[Build Semantic Layer]
        A3[Publish Curated Panel]
    end

    subgraph DS[Data Science]
        B1[Define Targets]
        B2[Engineer Features]
        B3[Train Validate Model]
        B4[Publish Drivers]
    end

    subgraph BI[Analytics Product / BI]
        C1[Build Dashboards]
        C2[Create Scenario Views]
        C3[Support Agent Outputs]
    end

    subgraph BU[Business Stakeholders]
        D1[Validate Definitions]
        D2[Review Outputs]
        D3[Adopt Decisions]
    end

    A1 --> A2 --> A3 --> B1 --> B2 --> B3 --> B4 --> C1 --> C2 --> C3
    D1 --> B1
    D2 --> C1
    D3 --> C2
```

## Notes

- These diagrams are intended to support planning and communication, not replace the written blueprint.
- If the team prefers, these can later be split into separate architecture, modeling, and operating docs.
- Mermaid rendering depends on IDE support. If a viewer does not render Mermaid, the source blocks can still be maintained as documentation.
