# BUILT Cannibalization Mermaid Diagrams

This artifact visualizes the proposed BUILT cannibalization experience using Mermaid.

It is designed around the product pattern we want:

- deterministic evidence first
- ML scoring and event detection as a powerful support layer
- explanation, provenance, and lineage exposed in a disciplined way
- polished user-facing decisions for assortment and product-mix optimization

## 1. End-to-End Product Flow

```mermaid
flowchart TD
    A[SPINS POS Data<br/>All_items_extract style fields] --> B[Product Enrichment Layer<br/>Specific flavor, pack size, hierarchy]
    B --> C[Deterministic Comparison Layer<br/>Geography, donor pool, pre/post windows]
    C --> D[Evidence Metrics Layer<br/>Base Units, Units, TDP, Units/TDP, ARP]
    C --> E[ML Scoring Layer<br/>Cannibalization risk, donor ranking, incrementality]
    D --> F[Explanation Layer]
    E --> F
    E --> G[Significant Event Layer<br/>Launch risk, donor decline, distribution-led gain]
    F --> H[Provenance Layer<br/>Data source, time window, donor logic, model version]
    G --> I[User-Facing Views]
    H --> I
    D --> I
    I --> J[Assortment Action<br/>Keep, Expand, Monitor, Reduce, Replace]
```

## 2. Deterministic Plus ML Decision Pattern

```mermaid
flowchart LR
    A[User selects focal SKU] --> B[Apply deterministic rules]
    B --> C[Build candidate donor set]
    C --> D[Calculate evidence metrics]
    C --> E[Run ML ranking and scoring]
    D --> F[Generate business explanation]
    E --> F
    E --> G[Detect significant events]
    F --> H[Attach provenance and lineage]
    G --> H
    H --> I[Surface status and recommended action]
```

## 3. New SKU / New Pack Cannibalization View

```mermaid
flowchart TD
    A[Focal launch SKU] --> B{Same specific flavor?}
    B -->|Yes| C[Same flavor donor pool]
    B -->|No| D[Same family / nearby substitute donor pool]
    C --> E[Split by geography]
    D --> E
    E --> F[Compare pre vs post launch]
    F --> G[Base Units change]
    F --> H[Units change]
    F --> I[TDP change]
    F --> J[Units/TDP change]
    G --> K[ML cannibalization score]
    H --> K
    I --> K
    J --> K
    K --> L[Status by geography<br/>Incremental / Neutral / Watch / Cannibalizing]
```

## 4. Same Specific Flavor Pack-Size Ladder

```mermaid
flowchart TD
    A[Specific flavor selected<br/>ex: Mint Brownie] --> B[Find all BUILT SKUs with same specific flavor]
    B --> C[Split by pack count / size]
    C --> D[Show Base Units]
    C --> E[Show Units]
    C --> F[Show TDP]
    C --> G[Show Units/TDP]
    D --> H[Evaluate donor / recipient pattern]
    E --> H
    F --> H
    G --> H
    H --> I[Assortment insight<br/>Keep multiple sizes / reduce overlap / expand winner]
```

## 5. Geography Heatmap Logic

```mermaid
flowchart TD
    A[Geography-level focal SKU results] --> B[Base Units trend]
    A --> C[Units trend]
    A --> D[TDP trend]
    A --> E[Units/TDP trend]
    B --> F{Interpretation}
    C --> F
    D --> F
    E --> F
    F -->|Demand up, productivity up| G[Green<br/>Likely incremental]
    F -->|Demand mixed, reach up| H[Yellow<br/>Monitor]
    F -->|Donor decline plus weak productivity| I[Red<br/>Likely cannibalizing]
```

## 6. Significant Event Callout Flow

```mermaid
flowchart LR
    A[Weekly or period metrics] --> B[Event detection rules]
    A --> C[ML event significance model]
    B --> D[Candidate event]
    C --> D
    D --> E{Evidence threshold met?}
    E -->|No| F[Suppress event]
    E -->|Yes| G[Surface event callout]
    G --> H[Attach explanation]
    G --> I[Attach provenance]
```

## 7. Provenance Panel Structure

```mermaid
flowchart TD
    A[Surfaced recommendation] --> B[Data source]
    A --> C[Time window used]
    A --> D[Geography scope]
    A --> E[Donor pool logic]
    A --> F[Model version]
    A --> G[Score timestamp]
    A --> H[Top drivers]
    B --> I[User can inspect lineage]
    C --> I
    D --> I
    E --> I
    F --> I
    G --> I
    H --> I
```

## 8. Screen-to-Screen UX Flow

```mermaid
flowchart LR
    A[Landing page<br/>priority events] --> B[Geography view]
    B --> C[Specific flavor / pack ladder]
    C --> D[Pre/post launch diagnostic]
    D --> E[Provenance and explanation drawer]
    E --> F[Assortment action recommendation]
```

## Recommended use

These diagrams are best paired with:

- [brad_built_cannibalization_view_wireframes_and_formulas.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_view_wireframes_and_formulas.md)
- [brad_built_ml_role_in_deterministic_cannibalization_tool.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_ml_role_in_deterministic_cannibalization_tool.md)
- [brad_built_cannibalization_views_for_assortment.md](/Users/jasonbrazeal/Documents/FirstAgent/docs/brad_built_cannibalization_views_for_assortment.md)
