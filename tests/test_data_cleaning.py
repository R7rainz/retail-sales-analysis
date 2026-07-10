from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data_cleaning import RetailDataCleaner  # noqa: E402


def test_clean_data_standardizes_dates_numbers_and_duplicates() -> None:
    raw = pd.DataFrame(
        {
            "Row ID": [1, 1, 2],
            "Order ID": [100, 100, 101],
            "Order Date": ["10/13/2010", "10/13/2010", 40918],
            "Order Priority": ["High", "High", None],
            "Order Quantity": ["2", "2", "4"],
            "Sales": ["1,000.50", "1,000.50", None],
            "Discount": ["5", "5", None],
            "Profit": [120.0, 120.0, None],
            "Unit Price": ["500.25", "500.25", "25"],
            "Shipping Cost": ["10", "10", None],
            "Customer Name": ["A", "A", None],
            "Province": ["X", "X", "Y"],
            "Region": ["West", "West", "East"],
            "Customer Segment": ["Consumer", "Consumer", "Corporate"],
            "Product Category": ["Technology", "Technology", "Furniture"],
            "Product Sub-Category": ["Phones", "Phones", "Chairs"],
            "Product Name": ["Phone", "Phone", "Chair"],
            "Product Container": ["Box", "Box", "Wrap"],
            "Product Base Margin": [0.5, 0.5, None],
            "Ship Mode": ["Regular Air", "Regular Air", "Truck"],
            "Ship Date": ["10/14/2010", "10/14/2010", 40920],
        }
    )

    cleaner = RetailDataCleaner()
    cleaned, summary = cleaner.clean_data(raw)

    assert len(cleaned) == 2
    assert summary.duplicates_removed == 1
    assert cleaned.columns.tolist()[0] == "row_id"
    assert cleaned["order_date"].notna().all()
    assert cleaned["ship_date"].notna().all()
    assert cleaned["discount"].max() <= 1
    assert cleaned["sales"].isna().sum() == 0
    assert "Unknown" in cleaned["order_priority"].tolist()

