"""Chart generation for the Retail Sales & Profit Analysis project."""

from __future__ import annotations

import os
import sys
from pathlib import Path

MPLCONFIGDIR = (
    Path(__file__).resolve().parents[1]
    / "output"
    / "dashboard_assets"
    / "matplotlib_cache"
)
MPLCONFIGDIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("MPLCONFIGDIR", str(MPLCONFIGDIR))

import matplotlib.pyplot as plt
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import seaborn as sns

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.analysis import RetailSalesAnalyzer, prepare_cleaned_data  # noqa: E402
from src.utils import CHARTS_DIR, ensure_directories, safe_filename  # noqa: E402


class RetailVisualizer:
    """Build interactive Plotly charts and static chart exports."""

    color_sequence = [
        "#2563eb",
        "#16a34a",
        "#dc2626",
        "#9333ea",
        "#f59e0b",
        "#0891b2",
        "#4f46e5",
        "#be123c",
    ]

    def __init__(self, dataframe: pd.DataFrame) -> None:
        self.dataframe = dataframe.copy()
        self.analyzer = RetailSalesAnalyzer(self.dataframe)

    def build_figures(self) -> dict[str, go.Figure]:
        """Return all dashboard and export figures."""
        return {
            "sales_by_region": self.sales_by_region(),
            "sales_by_product_category": self.sales_by_product_category(),
            "top_products_by_sales": self.top_products_by_sales(),
            "monthly_sales_trend": self.monthly_sales_trend(),
            "profit_by_customer_segment": self.profit_by_customer_segment(),
            "sales_by_order_priority": self.sales_by_order_priority(),
        }

    def sales_by_region(self) -> go.Figure:
        data = self.analyzer.sales_by_region()
        return self._bar_chart(
            data,
            x="region",
            y="total_sales",
            title="Sales by Region",
            labels={"region": "Region", "total_sales": "Sales"},
        )

    def sales_by_product_category(self) -> go.Figure:
        data = self.analyzer.sales_by_product_category()
        return self._bar_chart(
            data,
            x="product_category",
            y="total_sales",
            title="Sales by Product Category",
            labels={"product_category": "Category", "total_sales": "Sales"},
        )

    def top_products_by_sales(self, limit: int = 10) -> go.Figure:
        data = self.analyzer.top_products_by_sales(limit).sort_values("total_sales")
        if data.empty:
            return self._empty_figure("Top Products by Sales")

        fig = px.bar(
            data,
            x="total_sales",
            y="product_name",
            orientation="h",
            title="Top Products by Sales",
            labels={"product_name": "Product", "total_sales": "Sales"},
            color_discrete_sequence=self.color_sequence,
        )
        return self._style_figure(fig)

    def monthly_sales_trend(self) -> go.Figure:
        data = self.analyzer.monthly_sales_trend()
        if data.empty:
            return self._empty_figure("Monthly Sales Trend")

        fig = px.line(
            data,
            x="month",
            y="total_sales",
            markers=True,
            title="Monthly Sales Trend",
            labels={"month": "Month", "total_sales": "Sales"},
            color_discrete_sequence=["#2563eb"],
        )
        fig.update_traces(line_width=3)
        return self._style_figure(fig)

    def profit_by_customer_segment(self) -> go.Figure:
        data = self.analyzer.profit_by_customer_segment()
        return self._bar_chart(
            data,
            x="customer_segment",
            y="total_profit",
            title="Profit by Customer Segment",
            labels={"customer_segment": "Customer Segment", "total_profit": "Profit"},
        )

    def sales_by_order_priority(self) -> go.Figure:
        data = self.analyzer.sales_by_order_priority()
        return self._bar_chart(
            data,
            x="order_priority",
            y="total_sales",
            title="Sales by Order Priority",
            labels={"order_priority": "Order Priority", "total_sales": "Sales"},
        )

    def save_all_charts(self, output_dir: Path | str = CHARTS_DIR) -> list[Path]:
        """Save all charts as interactive HTML and static PNG files."""
        ensure_directories()
        chart_dir = Path(output_dir)
        chart_dir.mkdir(parents=True, exist_ok=True)
        saved_paths: list[Path] = []

        for name, figure in self.build_figures().items():
            html_path = chart_dir / f"{safe_filename(name)}.html"
            figure.write_html(html_path, include_plotlyjs="cdn", full_html=True)
            saved_paths.append(html_path)

        saved_paths.extend(self._save_static_pngs(chart_dir))
        return saved_paths

    def _bar_chart(
        self,
        dataframe: pd.DataFrame,
        x: str,
        y: str,
        title: str,
        labels: dict[str, str],
    ) -> go.Figure:
        if dataframe.empty:
            return self._empty_figure(title)

        fig = px.bar(
            dataframe,
            x=x,
            y=y,
            title=title,
            labels=labels,
            color=x,
            color_discrete_sequence=self.color_sequence,
        )
        fig.update_layout(showlegend=False)
        return self._style_figure(fig)

    @staticmethod
    def _style_figure(figure: go.Figure) -> go.Figure:
        figure.update_layout(
            template="plotly_white",
            title_x=0.02,
            margin=dict(l=30, r=30, t=70, b=40),
            hovermode="closest",
            font=dict(family="Arial, sans-serif", size=13),
        )
        figure.update_yaxes(tickformat=",.0f")
        return figure

    @staticmethod
    def _empty_figure(title: str) -> go.Figure:
        figure = go.Figure()
        figure.update_layout(
            template="plotly_white",
            title=title,
            xaxis={"visible": False},
            yaxis={"visible": False},
            annotations=[
                {
                    "text": "No data available",
                    "xref": "paper",
                    "yref": "paper",
                    "showarrow": False,
                    "font": {"size": 16},
                }
            ],
        )
        return figure

    def _save_static_pngs(self, chart_dir: Path) -> list[Path]:
        sns.set_theme(style="whitegrid")
        saved_paths: list[Path] = []

        static_specs = [
            (
                "sales_by_region",
                self.analyzer.sales_by_region(),
                "region",
                "total_sales",
                "Sales by Region",
                False,
            ),
            (
                "sales_by_product_category",
                self.analyzer.sales_by_product_category(),
                "product_category",
                "total_sales",
                "Sales by Product Category",
                False,
            ),
            (
                "top_products_by_sales",
                self.analyzer.top_products_by_sales(10),
                "total_sales",
                "product_name",
                "Top Products by Sales",
                True,
            ),
            (
                "profit_by_customer_segment",
                self.analyzer.profit_by_customer_segment(),
                "customer_segment",
                "total_profit",
                "Profit by Customer Segment",
                False,
            ),
            (
                "sales_by_order_priority",
                self.analyzer.sales_by_order_priority(),
                "order_priority",
                "total_sales",
                "Sales by Order Priority",
                False,
            ),
        ]

        for name, data, x_column, y_column, title, horizontal in static_specs:
            if data.empty:
                continue

            path = chart_dir / f"{safe_filename(name)}.png"
            plt.figure(figsize=(11, 6))
            if horizontal:
                plot_data = data.sort_values(x_column)
                sns.barplot(data=plot_data, x=x_column, y=y_column, hue=y_column, legend=False)
            else:
                sns.barplot(data=data, x=x_column, y=y_column, hue=x_column, legend=False)
                plt.xticks(rotation=25, ha="right")

            plt.title(title)
            plt.tight_layout()
            plt.savefig(path, dpi=150, bbox_inches="tight")
            plt.close()
            saved_paths.append(path)

        monthly = self.analyzer.monthly_sales_trend()
        if not monthly.empty:
            path = chart_dir / "monthly_sales_trend.png"
            plt.figure(figsize=(12, 6))
            sns.lineplot(data=monthly, x="month", y="total_sales", marker="o")
            plt.title("Monthly Sales Trend")
            plt.xticks(rotation=35, ha="right")
            plt.tight_layout()
            plt.savefig(path, dpi=150, bbox_inches="tight")
            plt.close()
            saved_paths.append(path)

        return saved_paths


def generate_all_charts(dataframe: pd.DataFrame, output_dir: Path | str = CHARTS_DIR) -> list[Path]:
    """Generate all assignment-required charts and save them to disk."""
    visualizer = RetailVisualizer(dataframe)
    return visualizer.save_all_charts(output_dir)


def main() -> None:
    """Generate all charts from the cleaned dataset."""
    dataframe = prepare_cleaned_data()
    paths = generate_all_charts(dataframe)
    print(f"Generated {len(paths)} chart files.")
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
