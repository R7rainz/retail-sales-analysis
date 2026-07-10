# Retail Sales & Profit Analysis

A complete Python project for cleaning retail sales data, generating analysis outputs, creating charts, producing a business insights report, and launching an interactive Streamlit dashboard.

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

