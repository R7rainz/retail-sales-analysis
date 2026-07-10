"""Analysis and business insight generation for retail sales data."""

from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.data_cleaning import RetailDataCleaner  # noqa: E402
from src.utils import (  # noqa: E402
    ANALYSIS_TABLES_FILE,
    CLEANED_DATA_FILE,
    REPORT_FILE,
    dataframe_to_markdown,
    ensure_directories,
    format_currency,
    format_percent,
    load_cleaned_dataset,
    validate_required_columns,
)


class RetailSalesAnalyzer:
    """Compute KPIs, grouped analyses, and business insights."""

    def __init__(self, dataframe: pd.DataFrame) -> None:
        if dataframe.empty:
            raise ValueError("Cannot analyze an empty dataset.")

        self.dataframe = dataframe.copy()
        self.dataframe["order_date"] = pd.to_datetime(
            self.dataframe["order_date"], errors="coerce"
        )
        validate_required_columns(self.dataframe)

    @classmethod
    def from_cleaned_data(cls, path: Path | str = CLEANED_DATA_FILE) -> "RetailSalesAnalyzer":
        """Load a cleaned dataset and create an analyzer instance."""
        return cls(load_cleaned_dataset(path))

    def calculate_kpis(self) -> dict[str, float | int]:
        """Calculate headline retail performance KPIs."""
        return {
            "total_sales": float(self.dataframe["sales"].sum()),
            "total_profit": float(self.dataframe["profit"].sum()),
            "total_orders": int(self.dataframe["order_id"].nunique()),
            "average_discount": float(self.dataframe["discount"].mean()),
            "total_shipping_cost": float(self.dataframe["shipping_cost"].sum()),
        }

    def sales_by_region(self) -> pd.DataFrame:
        """Aggregate total sales by region."""
        return self._sum_by("region", "sales", "total_sales")

    def sales_by_product_category(self) -> pd.DataFrame:
        """Aggregate total sales by product category."""
        return self._sum_by("product_category", "sales", "total_sales")

    def top_products_by_sales(self, limit: int = 10) -> pd.DataFrame:
        """Return the highest revenue products."""
        grouped = self._sum_by("product_name", "sales", "total_sales")
        return grouped.head(limit).reset_index(drop=True)

    def profit_by_customer_segment(self) -> pd.DataFrame:
        """Aggregate total profit by customer segment."""
        return self._sum_by("customer_segment", "profit", "total_profit")

    def sales_by_order_priority(self) -> pd.DataFrame:
        """Aggregate total sales by order priority."""
        return self._sum_by("order_priority", "sales", "total_sales")

    def monthly_sales_trend(self) -> pd.DataFrame:
        """Aggregate sales, profit, and order count by order month."""
        monthly = (
            self.dataframe.dropna(subset=["order_date"])
            .assign(month=lambda frame: frame["order_date"].dt.to_period("M").dt.to_timestamp())
            .groupby("month", as_index=False)
            .agg(
                total_sales=("sales", "sum"),
                total_profit=("profit", "sum"),
                total_orders=("order_id", "nunique"),
            )
            .sort_values("month")
            .reset_index(drop=True)
        )
        return monthly

    def profit_by_product_category(self) -> pd.DataFrame:
        """Aggregate total profit by product category."""
        return self._sum_by("product_category", "profit", "total_profit")

    def analysis_tables(self) -> dict[str, pd.DataFrame]:
        """Return all assignment-required analysis tables."""
        return {
            "sales_by_region": self.sales_by_region(),
            "sales_by_product_category": self.sales_by_product_category(),
            "top_10_products_by_sales": self.top_products_by_sales(10),
            "profit_by_customer_segment": self.profit_by_customer_segment(),
            "sales_by_order_priority": self.sales_by_order_priority(),
            "monthly_sales_trend": self.monthly_sales_trend(),
            "profit_by_product_category": self.profit_by_product_category(),
        }

    def generate_insights(self) -> dict[str, Any]:
        """Generate direct answers to the required business questions."""
        sales_region = self.sales_by_region()
        profit_category = self.profit_by_product_category()
        top_products = self.top_products_by_sales(10)
        profit_segment = self.profit_by_customer_segment()
        monthly = self.monthly_sales_trend()

        insights: dict[str, Any] = {
            "highest_sales_region": self._top_record(sales_region, "region", "total_sales"),
            "most_profitable_category": self._top_record(
                profit_category, "product_category", "total_profit"
            ),
            "highest_revenue_products": top_products,
            "most_profitable_customer_segment": self._top_record(
                profit_segment, "customer_segment", "total_profit"
            ),
            "monthly_sales_trend": self._describe_monthly_trend(monthly),
        }
        return insights

    def export_analysis_tables(
        self,
        path: Path | str = ANALYSIS_TABLES_FILE,
    ) -> Path:
        """Export the analysis tables to a multi-sheet Excel workbook."""
        ensure_directories()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
            for sheet_name, table in self.analysis_tables().items():
                safe_name = sheet_name[:31]
                table.to_excel(writer, sheet_name=safe_name, index=False)

        return output_path

    def generate_report(self, path: Path | str = REPORT_FILE) -> Path:
        """Generate a markdown report summarizing KPIs and business insights."""
        ensure_directories()
        output_path = Path(path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        kpis = self.calculate_kpis()
        insights = self.generate_insights()
        tables = self.analysis_tables()

        report = [
            "# Retail Sales & Profit Analysis Report",
            "",
            f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## KPI Summary",
            "",
            f"- Total Sales: {format_currency(kpis['total_sales'])}",
            f"- Total Profit: {format_currency(kpis['total_profit'])}",
            f"- Total Orders: {kpis['total_orders']:,}",
            f"- Average Discount: {format_percent(kpis['average_discount'])}",
            f"- Total Shipping Cost: {format_currency(kpis['total_shipping_cost'])}",
            "",
            "## Business Insights",
            "",
            self._format_insight_line(
                "Highest sales region",
                insights["highest_sales_region"],
                "total_sales",
            ),
            self._format_insight_line(
                "Most profitable category",
                insights["most_profitable_category"],
                "total_profit",
            ),
            self._format_insight_line(
                "Most profitable customer segment",
                insights["most_profitable_customer_segment"],
                "total_profit",
            ),
            f"- Monthly sales trend: {insights['monthly_sales_trend']}",
            "",
            "## Highest Revenue Products",
            "",
            dataframe_to_markdown(tables["top_10_products_by_sales"], max_rows=10),
            "",
            "## Sales By Region",
            "",
            dataframe_to_markdown(tables["sales_by_region"]),
            "",
            "## Sales By Product Category",
            "",
            dataframe_to_markdown(tables["sales_by_product_category"]),
            "",
            "## Profit By Customer Segment",
            "",
            dataframe_to_markdown(tables["profit_by_customer_segment"]),
            "",
            "## Sales By Order Priority",
            "",
            dataframe_to_markdown(tables["sales_by_order_priority"]),
            "",
            "## Monthly Sales Trend",
            "",
            dataframe_to_markdown(tables["monthly_sales_trend"], max_rows=24),
            "",
        ]

        output_path.write_text("\n".join(report), encoding="utf-8")
        return output_path

    def _sum_by(self, group_column: str, value_column: str, output_column: str) -> pd.DataFrame:
        grouped = (
            self.dataframe.groupby(group_column, dropna=False, as_index=False)[value_column]
            .sum()
            .rename(columns={value_column: output_column})
            .sort_values(output_column, ascending=False)
            .reset_index(drop=True)
        )
        return grouped

    @staticmethod
    def _top_record(dataframe: pd.DataFrame, label_column: str, value_column: str) -> dict[str, Any]:
        if dataframe.empty:
            return {"label": "No data", "value": 0.0}

        row = dataframe.sort_values(value_column, ascending=False).iloc[0]
        return {"label": row[label_column], "value": float(row[value_column])}

    @staticmethod
    def _describe_monthly_trend(monthly: pd.DataFrame) -> str:
        if monthly.empty:
            return "No dated sales records were available."
        if len(monthly) == 1:
            row = monthly.iloc[0]
            return (
                f"Only one month is available: {row['month'].strftime('%B %Y')} "
                f"with {format_currency(float(row['total_sales']))} in sales."
            )

        sales = monthly["total_sales"].to_numpy(dtype=float)
        x_axis = np.arange(len(sales))
        slope = float(np.polyfit(x_axis, sales, 1)[0])
        average_sales = float(np.mean(sales))
        tolerance = max(abs(average_sales) * 0.02, 1.0)

        if slope > tolerance:
            direction = "upward"
        elif slope < -tolerance:
            direction = "downward"
        else:
            direction = "relatively stable"

        best = monthly.loc[monthly["total_sales"].idxmax()]
        worst = monthly.loc[monthly["total_sales"].idxmin()]
        first = monthly.iloc[0]
        last = monthly.iloc[-1]

        return (
            f"The overall trend is {direction}. Sales moved from "
            f"{format_currency(float(first['total_sales']))} in "
            f"{first['month'].strftime('%B %Y')} to "
            f"{format_currency(float(last['total_sales']))} in "
            f"{last['month'].strftime('%B %Y')}. Peak sales occurred in "
            f"{best['month'].strftime('%B %Y')} at "
            f"{format_currency(float(best['total_sales']))}; the lowest month was "
            f"{worst['month'].strftime('%B %Y')} at "
            f"{format_currency(float(worst['total_sales']))}."
        )

    @staticmethod
    def _format_insight_line(label: str, insight: dict[str, Any], value_key: str) -> str:
        value = insight.get(value_key, insight.get("value", 0.0))
        return f"- {label}: {insight['label']} ({format_currency(float(value))})"


def prepare_cleaned_data(force: bool = False) -> pd.DataFrame:
    """Load cleaned data, generating it from raw data when needed."""
    if CLEANED_DATA_FILE.exists() and not force:
        return load_cleaned_dataset(CLEANED_DATA_FILE)

    cleaner = RetailDataCleaner()
    cleaned, _ = cleaner.run()
    return cleaned


def run_full_analysis() -> tuple[Path, Path, list[Path]]:
    """Run cleaning, analysis exports, report generation, and chart generation."""
    dataframe = prepare_cleaned_data(force=True)
    analyzer = RetailSalesAnalyzer(dataframe)
    tables_path = analyzer.export_analysis_tables()
    report_path = analyzer.generate_report()

    from src.visualization import generate_all_charts

    chart_paths = generate_all_charts(dataframe)
    return report_path, tables_path, chart_paths


def main() -> None:
    """Run the complete analysis workflow from the command line."""
    report_path, tables_path, chart_paths = run_full_analysis()
    print("Analysis completed.")
    print(f"Report: {report_path}")
    print(f"Analysis tables: {tables_path}")
    print(f"Charts generated: {len(chart_paths)}")


if __name__ == "__main__":
    main()
