from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.analysis import RetailSalesAnalyzer  # noqa: E402


def test_analyzer_calculates_required_kpis_and_tables() -> None:
    data = pd.DataFrame(
        {
            "row_id": [1, 2, 3],
            "order_id": [10, 10, 11],
            "order_date": pd.to_datetime(["2024-01-05", "2024-01-20", "2024-02-10"]),
            "ship_date": pd.to_datetime(["2024-01-07", "2024-01-22", "2024-02-12"]),
            "order_priority": ["High", "Low", "High"],
            "order_quantity": [2, 1, 3],
            "sales": [100.0, 250.0, 400.0],
            "discount": [0.1, 0.0, 0.2],
            "profit": [20.0, 50.0, 100.0],
            "unit_price": [50.0, 250.0, 133.33],
            "shipping_cost": [5.0, 10.0, 15.0],
            "customer_name": ["A", "B", "C"],
            "customer_segment": ["Consumer", "Corporate", "Corporate"],
            "region": ["West", "East", "East"],
            "province": ["P1", "P2", "P2"],
            "ship_mode": ["Air", "Truck", "Truck"],
            "product_category": ["Technology", "Furniture", "Furniture"],
            "product_sub_category": ["Phones", "Chairs", "Tables"],
            "product_name": ["Phone", "Chair", "Table"],
            "product_container": ["Box", "Wrap", "Crate"],
            "product_base_margin": [0.4, 0.5, 0.6],
        }
    )

    analyzer = RetailSalesAnalyzer(data)
    kpis = analyzer.calculate_kpis()

    assert kpis["total_sales"] == 750.0
    assert kpis["total_profit"] == 170.0
    assert kpis["total_orders"] == 2
    assert round(kpis["average_discount"], 4) == 0.1
    assert kpis["total_shipping_cost"] == 30.0
    assert analyzer.sales_by_region().iloc[0]["region"] == "East"
    assert len(analyzer.monthly_sales_trend()) == 2
