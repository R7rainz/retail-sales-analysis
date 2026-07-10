"""Shared utilities for the Retail Sales & Profit Analysis project."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
OUTPUT_DIR = PROJECT_ROOT / "output"
CHARTS_DIR = OUTPUT_DIR / "charts"
REPORTS_DIR = OUTPUT_DIR / "reports"
DASHBOARD_ASSETS_DIR = OUTPUT_DIR / "dashboard_assets"

RAW_DATA_FILE = RAW_DATA_DIR / "retail_sales_raw.xlsx"
CLEANED_DATA_FILE = CLEANED_DATA_DIR / "retail_sales_cleaned.csv"
CLEANED_EXCEL_FILE = CLEANED_DATA_DIR / "retail_sales_cleaned.xlsx"
REPORT_FILE = REPORTS_DIR / "business_insights_report.md"
ANALYSIS_TABLES_FILE = REPORTS_DIR / "analysis_tables.xlsx"

DATE_COLUMNS = ["order_date", "ship_date"]
INTEGER_COLUMNS = ["row_id", "order_id", "order_quantity"]
NUMERIC_COLUMNS = [
    "row_id",
    "order_id",
    "order_quantity",
    "sales",
    "discount",
    "profit",
    "unit_price",
    "shipping_cost",
    "product_base_margin",
]
CATEGORICAL_COLUMNS = [
    "order_priority",
    "ship_mode",
    "customer_name",
    "province",
    "region",
    "customer_segment",
    "product_category",
    "product_sub_category",
    "product_name",
    "product_container",
]
REQUIRED_COLUMNS = [
    "order_id",
    "order_date",
    "order_priority",
    "sales",
    "discount",
    "profit",
    "shipping_cost",
    "region",
    "customer_segment",
    "product_category",
    "product_name",
    "ship_date",
]


def ensure_directories() -> None:
    """Create all project output directories if they do not already exist."""
    for directory in [
        RAW_DATA_DIR,
        CLEANED_DATA_DIR,
        CHARTS_DIR,
        REPORTS_DIR,
        DASHBOARD_ASSETS_DIR,
    ]:
        directory.mkdir(parents=True, exist_ok=True)


def standardize_column_name(column_name: object) -> str:
    """Convert a source column name to a stable snake_case identifier."""
    name = str(column_name).strip().lower()
    name = re.sub(r"[^0-9a-zA-Z]+", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name


def standardize_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Return a copy of a dataframe with standardized, unique column names."""
    renamed = dataframe.copy()
    seen: dict[str, int] = {}
    columns: list[str] = []

    for column in renamed.columns:
        base_name = standardize_column_name(column)
        count = seen.get(base_name, 0)
        seen[base_name] = count + 1
        columns.append(base_name if count == 0 else f"{base_name}_{count + 1}")

    renamed.columns = columns
    return renamed


def find_raw_dataset() -> Path:
    """Find the raw retail dataset in the project data folder or root folder."""
    if RAW_DATA_FILE.exists():
        return RAW_DATA_FILE

    candidates = [
        *sorted(RAW_DATA_DIR.glob("*.xlsx")),
        *sorted(RAW_DATA_DIR.glob("*.xls")),
        *sorted(RAW_DATA_DIR.glob("*.csv")),
        *sorted(PROJECT_ROOT.glob("*.xlsx")),
        *sorted(PROJECT_ROOT.glob("*.xls")),
        *sorted(PROJECT_ROOT.glob("*.csv")),
    ]
    if not candidates:
        raise FileNotFoundError(
            "No raw dataset found. Place an Excel or CSV file in data/raw/."
        )
    return candidates[0]


def read_dataset(path: Path | str) -> pd.DataFrame:
    """Read a CSV or Excel dataset into a pandas dataframe."""
    dataset_path = Path(path)
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    suffix = dataset_path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(dataset_path)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(dataset_path, sheet_name=0)

    raise ValueError(f"Unsupported dataset format: {dataset_path.suffix}")


def load_cleaned_dataset(path: Path | str = CLEANED_DATA_FILE) -> pd.DataFrame:
    """Load the cleaned dataset and parse date columns when present."""
    cleaned_path = Path(path)
    if not cleaned_path.exists():
        raise FileNotFoundError(f"Cleaned dataset not found: {cleaned_path}")

    dataframe = pd.read_csv(cleaned_path)
    for column in DATE_COLUMNS:
        if column in dataframe.columns:
            dataframe[column] = pd.to_datetime(dataframe[column], errors="coerce")
    return dataframe


def validate_required_columns(
    dataframe: pd.DataFrame,
    required_columns: Iterable[str] = REQUIRED_COLUMNS,
) -> None:
    """Raise a clear error if required analysis columns are unavailable."""
    missing = [column for column in required_columns if column not in dataframe.columns]
    if missing:
        formatted = ", ".join(missing)
        raise ValueError(f"Missing required columns after cleaning: {formatted}")


def format_currency(value: float) -> str:
    """Format a numeric value as a compact currency string."""
    return f"${value:,.2f}"


def format_percent(value: float) -> str:
    """Format a decimal value as a percentage string."""
    return f"{value:.2%}"


def dataframe_to_markdown(dataframe: pd.DataFrame, max_rows: int = 20) -> str:
    """Create a markdown table without relying on optional tabulate support."""
    if dataframe.empty:
        return "_No data available._"

    preview = dataframe.head(max_rows).copy()
    for column in preview.columns:
        preview[column] = preview[column].map(
            lambda value, current_column=column: _format_markdown_value(
                current_column,
                value,
            )
        )

    preview = preview.rename(
        columns={column: column.replace("_", " ").title() for column in preview.columns}
    )

    headers = [str(column) for column in preview.columns]
    separator = ["---"] * len(headers)
    rows = preview.values.tolist()

    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(separator) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)

    if len(dataframe) > max_rows:
        lines.append(f"\n_Showing first {max_rows} of {len(dataframe)} rows._")

    return "\n".join(lines)


def _format_markdown_value(column: str, value: Any) -> str:
    """Format report table values for readable markdown output."""
    if pd.isna(value):
        return ""

    lowered = column.lower()
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
        if any(token in lowered for token in ["sales", "profit", "cost", "price"]):
            return format_currency(numeric_value)
        if "discount" in lowered or "margin" in lowered:
            return format_percent(numeric_value)
        if any(token in lowered for token in ["orders", "quantity", "row_id", "order_id"]):
            return f"{numeric_value:,.0f}"
        return f"{numeric_value:,.2f}"

    return str(value)


def safe_filename(name: str) -> str:
    """Convert a display label into a filesystem-safe filename stem."""
    cleaned = re.sub(r"[^0-9a-zA-Z]+", "_", name.strip().lower())
    return re.sub(r"_+", "_", cleaned).strip("_")
