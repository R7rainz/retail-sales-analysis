"""Streamlit dashboard for Retail Sales & Profit Analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.analysis import RetailSalesAnalyzer, prepare_cleaned_data  # noqa: E402
from src.utils import REPORT_FILE, format_currency, format_percent  # noqa: E402
from src.visualization import RetailVisualizer  # noqa: E402


@st.cache_data(show_spinner=False)
def load_data() -> pd.DataFrame:
    """Load cleaned dashboard data, creating it from raw data when necessary."""
    return prepare_cleaned_data()


def filter_data(dataframe: pd.DataFrame) -> pd.DataFrame:
    """Render visible dashboard filters and return the filtered dataframe."""
    regions = _sorted_options(dataframe, "region")
    categories = _sorted_options(dataframe, "product_category")
    sub_categories = _sorted_options(dataframe, "product_sub_category")
    products = _sorted_options(dataframe, "product_name")
    segments = _sorted_options(dataframe, "customer_segment")
    priorities = _sorted_options(dataframe, "order_priority")
    ship_modes = _sorted_options(dataframe, "ship_mode")
    provinces = _sorted_options(dataframe, "province")
    min_date = dataframe["order_date"].min().date()
    max_date = dataframe["order_date"].max().date()

    with st.expander("Filters", expanded=True):
        first_row = st.columns(4)
        second_row = st.columns(4)
        third_row = st.columns(2)

        selected_regions = first_row[0].multiselect(
            "Region",
            regions,
            placeholder="Select regions",
        )
        selected_categories = first_row[1].multiselect(
            "Category",
            categories,
            placeholder="Select categories",
        )
        selected_sub_categories = first_row[2].multiselect(
            "Sub-Category",
            sub_categories,
            placeholder="Select sub-categories",
        )
        selected_segments = first_row[3].multiselect(
            "Customer Segment",
            segments,
            placeholder="Select segments",
        )
        selected_priorities = second_row[0].multiselect(
            "Order Priority",
            priorities,
            placeholder="Select priorities",
        )
        selected_ship_modes = second_row[1].multiselect(
            "Ship Mode",
            ship_modes,
            placeholder="Select ship modes",
        )
        selected_provinces = second_row[2].multiselect(
            "Province",
            provinces,
            placeholder="Select provinces",
        )
        selected_products = second_row[3].multiselect(
            "Product",
            products,
            placeholder="Select products",
        )
        selected_date_range = third_row[0].date_input(
            "Date Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
        )

    start_date, end_date = _parse_date_range(selected_date_range, min_date, max_date)
    mask = dataframe["order_date"].dt.date.between(start_date, end_date)

    optional_filters = {
        "region": selected_regions,
        "product_category": selected_categories,
        "product_sub_category": selected_sub_categories,
        "product_name": selected_products,
        "customer_segment": selected_segments,
        "order_priority": selected_priorities,
        "ship_mode": selected_ship_modes,
        "province": selected_provinces,
    }
    for column, selected_values in optional_filters.items():
        if selected_values:
            mask &= dataframe[column].astype(str).isin(selected_values)

    return dataframe.loc[mask].copy()


def render_kpis(analyzer: RetailSalesAnalyzer) -> None:
    """Render KPI cards."""
    kpis = analyzer.calculate_kpis()
    metric_columns = st.columns(5)
    metric_columns[0].metric("Total Sales", format_currency(kpis["total_sales"]))
    metric_columns[1].metric("Total Profit", format_currency(kpis["total_profit"]))
    metric_columns[2].metric("Total Orders", f"{kpis['total_orders']:,}")
    metric_columns[3].metric("Average Discount", format_percent(kpis["average_discount"]))
    metric_columns[4].metric(
        "Total Shipping Cost", format_currency(kpis["total_shipping_cost"])
    )


def render_charts(dataframe: pd.DataFrame) -> None:
    """Render all required charts."""
    visualizer = RetailVisualizer(dataframe)
    figures = visualizer.build_figures()

    left, right = st.columns(2)
    with left:
        st.plotly_chart(figures["sales_by_region"], use_container_width=True)
        st.plotly_chart(figures["top_products_by_sales"], use_container_width=True)
        st.plotly_chart(figures["profit_by_customer_segment"], use_container_width=True)
    with right:
        st.plotly_chart(figures["sales_by_product_category"], use_container_width=True)
        st.plotly_chart(figures["monthly_sales_trend"], use_container_width=True)
        st.plotly_chart(figures["sales_by_order_priority"], use_container_width=True)


def render_insights(analyzer: RetailSalesAnalyzer) -> None:
    """Render generated business insights."""
    insights = analyzer.generate_insights()

    st.subheader("Business Insights")
    insight_columns = st.columns(3)
    insight_columns[0].metric(
        "Highest Sales Region",
        insights["highest_sales_region"]["label"],
        format_currency(insights["highest_sales_region"]["value"]),
    )
    insight_columns[1].metric(
        "Most Profitable Category",
        insights["most_profitable_category"]["label"],
        format_currency(insights["most_profitable_category"]["value"]),
    )
    insight_columns[2].metric(
        "Most Profitable Segment",
        insights["most_profitable_customer_segment"]["label"],
        format_currency(insights["most_profitable_customer_segment"]["value"]),
    )
    st.info(insights["monthly_sales_trend"])

    if REPORT_FILE.exists():
        st.download_button(
            "Download Business Insights Report",
            data=REPORT_FILE.read_bytes(),
            file_name=REPORT_FILE.name,
            mime="text/markdown",
        )


def render_business_questions(analyzer: RetailSalesAnalyzer) -> None:
    """Render direct answers to the required assignment questions."""
    insights = analyzer.generate_insights()
    top_products = insights["highest_revenue_products"].copy()
    top_products["total_sales"] = top_products["total_sales"].map(format_currency)
    top_products = top_products.rename(
        columns={
            "product_name": "Product",
            "total_sales": "Revenue",
        }
    )
    leading_products = ", ".join(top_products["Product"].head(3).tolist())

    st.subheader("Business Questions")
    answer_rows = [
        {
            "Question": "Which region generates the highest sales?",
            "Answer": (
                f"{insights['highest_sales_region']['label']} generates the highest "
                f"sales at {format_currency(insights['highest_sales_region']['value'])}."
            ),
        },
        {
            "Question": "Which product category is the most profitable?",
            "Answer": (
                f"{insights['most_profitable_category']['label']} is the most "
                f"profitable category at "
                f"{format_currency(insights['most_profitable_category']['value'])}."
            ),
        },
        {
            "Question": "Which products generate the highest revenue?",
            "Answer": f"The leading revenue products are {leading_products}.",
        },
        {
            "Question": "Which customer segment contributes the most profit?",
            "Answer": (
                f"{insights['most_profitable_customer_segment']['label']} contributes "
                f"the most profit at "
                f"{format_currency(insights['most_profitable_customer_segment']['value'])}."
            ),
        },
        {
            "Question": "What is the monthly sales trend?",
            "Answer": insights["monthly_sales_trend"],
        },
    ]
    st.dataframe(
        pd.DataFrame(answer_rows),
        hide_index=True,
        use_container_width=True,
    )

    st.markdown("**Which products generate the highest revenue?**")
    st.dataframe(top_products, hide_index=True, use_container_width=True)


def _sorted_options(dataframe: pd.DataFrame, column: str) -> list[str]:
    return sorted(dataframe[column].dropna().astype(str).unique().tolist())


def _parse_date_range(
    selected_date_range: object,
    min_date: object,
    max_date: object,
) -> tuple[object, object]:
    if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
        return selected_date_range
    if isinstance(selected_date_range, list) and len(selected_date_range) == 2:
        return selected_date_range[0], selected_date_range[1]
    return min_date, max_date


def main() -> None:
    """Run the Streamlit dashboard."""
    st.set_page_config(
        page_title="Retail Sales & Profit Analysis",
        page_icon=":bar_chart:",
        layout="wide",
        initial_sidebar_state="collapsed",
    )

    st.title("Retail Sales & Profit Analysis")
    dataframe = load_data()
    filtered = filter_data(dataframe)

    if filtered.empty:
        st.warning("No records match the selected filters.")
        return

    analyzer = RetailSalesAnalyzer(filtered)
    analyzer.generate_report()
    render_kpis(analyzer)
    render_business_questions(analyzer)
    render_charts(filtered)
    render_insights(analyzer)


if __name__ == "__main__":
    main()
