# Retail Sales & Profit Analysis

### ▶ [**View the live interactive dashboard**](https://r7rainz.github.io/retail-sales-analysis/)

A complete Python project for cleaning retail sales data, generating analysis outputs, creating charts, producing a business insights report, and launching an interactive Streamlit dashboard.

## Dashboards

Two options, both driven by the same `RetailSalesAnalyzer`:

| | How to view | Best for |
| --- | --- | --- |
| **Static dashboard** | [Live on GitHub Pages](https://r7rainz.github.io/retail-sales-analysis/) — or `python src/build_static_dashboard.py`, then open `dashboard/index.html` | Sharing a link; no install, no server |
| **Streamlit dashboard** | `streamlit run app.py` | Local exploration with live filtering |

The static dashboard is a single self-contained HTML file with no external
requests, so it deploys straight to GitHub Pages and redeploys automatically
whenever `dashboard/` changes.

## Project Structure

```text
Retail-Sales-Analysis/
├── data/
│   ├── raw/
│   └── cleaned/
├── src/
│   ├── data_cleaning.py
│   ├── analysis.py
│   ├── visualization.py
│   ├── dashboard.py
│   └── utils.py
├── output/
│   ├── charts/
│   ├── reports/
│   └── dashboard_assets/
├── notebooks/
├── tests/
├── app.py
├── requirements.txt
├── README.md
└── .gitignore
```

## Setup

```bash
cd Retail-Sales-Analysis
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The raw dataset is already included at:

```text
data/raw/retail_sales_raw.xlsx
```

## Run The Full Pipeline

```bash
python -m src.analysis
```

This command automatically:

- cleans the raw dataset
- saves `data/cleaned/retail_sales_cleaned.csv`
- saves `data/cleaned/retail_sales_cleaned.xlsx`
- exports analysis tables to `output/reports/analysis_tables.xlsx`
- generates the business insights report at `output/reports/business_insights_report.md`
- generates interactive HTML and static PNG charts in `output/charts/`

## Run Individual Steps

```bash
python -m src.data_cleaning
python -m src.visualization
```

## Launch Dashboard

```bash
streamlit run app.py
```

The dashboard includes KPI cards, filters, charts, and generated business insights.

## Tests

```bash
pytest
```

