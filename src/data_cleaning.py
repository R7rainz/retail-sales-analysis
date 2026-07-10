"""Data cleaning pipeline for the Retail Sales & Profit Analysis project."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[1]))

from src.utils import (  # noqa: E402
    CATEGORICAL_COLUMNS,
    CLEANED_DATA_FILE,
    CLEANED_EXCEL_FILE,
    DATE_COLUMNS,
    INTEGER_COLUMNS,
    NUMERIC_COLUMNS,
    find_raw_dataset,
    read_dataset,
    ensure_directories,
    standardize_columns,
    validate_required_columns,
)


@dataclass(frozen=True)
class CleaningSummary:
    """Summary metadata from a cleaning run."""

    rows_before: int
    rows_after: int
    duplicates_removed: int
    missing_values_before: dict[str, int]
    missing_values_after: dict[str, int]
    cleaned_csv_path: Path
    cleaned_excel_path: Path


class RetailDataCleaner:
    """Clean raw retail sales data into an analysis-ready dataset."""

    def __init__(
        self,
        raw_path: Path | str | None = None,
        cleaned_csv_path: Path | str = CLEANED_DATA_FILE,
        cleaned_excel_path: Path | str = CLEANED_EXCEL_FILE,
    ) -> None:
        self.raw_path = Path(raw_path) if raw_path else None
        self.cleaned_csv_path = Path(cleaned_csv_path)
        self.cleaned_excel_path = Path(cleaned_excel_path)

    def load_raw_data(self) -> pd.DataFrame:
        """Load the raw dataset from disk."""
        dataset_path = self.raw_path or find_raw_dataset()
        try:
            return read_dataset(dataset_path)
        except Exception as exc:
            raise RuntimeError(f"Failed to load raw dataset from {dataset_path}: {exc}") from exc

    def clean_data(self, dataframe: pd.DataFrame) -> tuple[pd.DataFrame, CleaningSummary]:
        """Clean a raw retail dataframe and return the cleaned data plus summary."""
        if dataframe.empty:
            raise ValueError("The raw dataset is empty.")

        rows_before = len(dataframe)
        standardized = standardize_columns(dataframe)
        missing_before = self._missing_counts(standardized)

        cleaned = standardized.drop_duplicates().reset_index(drop=True)
        duplicates_removed = rows_before - len(cleaned)

        cleaned = self._clean_dates(cleaned)
        cleaned = self._clean_numeric_columns(cleaned)
        cleaned = self._clean_categorical_columns(cleaned)
        cleaned = self._repair_identifier_columns(cleaned)

        validate_required_columns(cleaned)
        cleaned = self._order_columns(cleaned)
        missing_after = self._missing_counts(cleaned)

        summary = CleaningSummary(
            rows_before=rows_before,
            rows_after=len(cleaned),
            duplicates_removed=duplicates_removed,
            missing_values_before=missing_before,
            missing_values_after=missing_after,
            cleaned_csv_path=self.cleaned_csv_path,
            cleaned_excel_path=self.cleaned_excel_path,
        )
        return cleaned, summary

    def save_cleaned_data(self, dataframe: pd.DataFrame) -> tuple[Path, Path]:
        """Save the cleaned dataset as CSV and Excel files."""
        ensure_directories()
        self.cleaned_csv_path.parent.mkdir(parents=True, exist_ok=True)
        dataframe.to_csv(self.cleaned_csv_path, index=False)
        dataframe.to_excel(self.cleaned_excel_path, index=False)
        return self.cleaned_csv_path, self.cleaned_excel_path

    def run(self) -> tuple[pd.DataFrame, CleaningSummary]:
        """Run the full cleaning pipeline and write cleaned outputs to disk."""
        raw = self.load_raw_data()
        cleaned, summary = self.clean_data(raw)
        csv_path, excel_path = self.save_cleaned_data(cleaned)
        updated_summary = CleaningSummary(
            rows_before=summary.rows_before,
            rows_after=summary.rows_after,
            duplicates_removed=summary.duplicates_removed,
            missing_values_before=summary.missing_values_before,
            missing_values_after=summary.missing_values_after,
            cleaned_csv_path=csv_path,
            cleaned_excel_path=excel_path,
        )
        return cleaned, updated_summary

    @staticmethod
    def _missing_counts(dataframe: pd.DataFrame) -> dict[str, int]:
        return dataframe.isna().sum().astype(int).to_dict()

    def _clean_dates(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = dataframe.copy()
        for column in DATE_COLUMNS:
            if column in cleaned.columns:
                cleaned[column] = self._parse_mixed_dates(cleaned[column])

        if {"order_date", "ship_date"}.issubset(cleaned.columns):
            cleaned["order_date"] = cleaned["order_date"].fillna(cleaned["ship_date"])
            cleaned["ship_date"] = cleaned["ship_date"].fillna(cleaned["order_date"])

        for column in DATE_COLUMNS:
            if column in cleaned.columns and cleaned[column].isna().any():
                fallback = cleaned[column].dropna().median()
                if pd.isna(fallback):
                    fallback = pd.Timestamp.today().normalize()
                cleaned[column] = cleaned[column].fillna(fallback)

        return cleaned

    @staticmethod
    def _parse_mixed_dates(series: pd.Series) -> pd.Series:
        """Parse text dates and Excel serial date values in the same column."""
        values = series.copy()
        parsed = pd.Series(pd.NaT, index=values.index, dtype="datetime64[ns]")
        numeric_values = pd.to_numeric(values, errors="coerce")
        excel_serial_mask = numeric_values.between(20_000, 80_000, inclusive="both")

        if excel_serial_mask.any():
            parsed.loc[excel_serial_mask] = pd.to_datetime(
                numeric_values.loc[excel_serial_mask],
                unit="D",
                origin="1899-12-30",
                errors="coerce",
            )

        text_mask = ~excel_serial_mask
        if text_mask.any():
            parsed.loc[text_mask] = pd.to_datetime(
                values.loc[text_mask],
                errors="coerce",
                dayfirst=False,
            )

        return parsed

    def _clean_numeric_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = dataframe.copy()

        for column in NUMERIC_COLUMNS:
            if column not in cleaned.columns:
                continue

            numeric = self._coerce_numeric(cleaned[column]).astype("float64")
            fill_value = self._numeric_fill_value(numeric, column)
            numeric = numeric.fillna(fill_value)

            if column == "discount":
                numeric = self._normalize_discount(numeric)
            elif column in {"sales", "shipping_cost", "order_quantity", "unit_price"}:
                numeric = numeric.clip(lower=0)

            if column in INTEGER_COLUMNS:
                numeric = numeric.round().astype("Int64")

            cleaned[column] = numeric

        return cleaned

    @staticmethod
    def _coerce_numeric(series: pd.Series) -> pd.Series:
        if pd.api.types.is_numeric_dtype(series):
            return pd.to_numeric(series, errors="coerce")

        as_text = (
            series.astype("string")
            .str.replace(",", "", regex=False)
            .str.replace("$", "", regex=False)
            .str.replace("%", "", regex=False)
            .str.strip()
        )
        return pd.to_numeric(as_text, errors="coerce")

    @staticmethod
    def _numeric_fill_value(series: pd.Series, column: str) -> float:
        if column in {"sales", "discount", "profit", "shipping_cost"}:
            return 0.0

        median = series.dropna().median()
        if pd.isna(median):
            return 0.0
        return float(median)

    @staticmethod
    def _normalize_discount(series: pd.Series) -> pd.Series:
        normalized = series.astype("float64").copy()
        percentage_mask = normalized.gt(1) & normalized.le(100)
        normalized.loc[percentage_mask] = normalized.loc[percentage_mask] / 100
        return normalized.clip(lower=0, upper=1)

    def _clean_categorical_columns(self, dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = dataframe.copy()

        for column in CATEGORICAL_COLUMNS:
            if column not in cleaned.columns:
                continue

            values = cleaned[column].astype("string").str.strip()
            invalid_mask = (
                values.isna()
                | values.eq("")
                | values.str.lower().isin({"nan", "none", "null", "na", "n/a"})
            )
            values = values.mask(invalid_mask, "Unknown")
            cleaned[column] = values.astype(str)

        return cleaned

    @staticmethod
    def _repair_identifier_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
        cleaned = dataframe.copy()

        if "row_id" not in cleaned.columns:
            cleaned["row_id"] = pd.Series(np.arange(1, len(cleaned) + 1), dtype="Int64")
        elif cleaned["row_id"].isna().any():
            missing = cleaned["row_id"].isna()
            cleaned.loc[missing, "row_id"] = np.arange(1, missing.sum() + 1)
            cleaned["row_id"] = cleaned["row_id"].astype("Int64")

        if "order_id" not in cleaned.columns:
            cleaned["order_id"] = cleaned["row_id"].astype("Int64")
        elif cleaned["order_id"].isna().any():
            cleaned["order_id"] = cleaned["order_id"].fillna(cleaned["row_id"]).astype("Int64")

        return cleaned

    @staticmethod
    def _order_columns(dataframe: pd.DataFrame) -> pd.DataFrame:
        preferred_order = [
            "row_id",
            "order_id",
            "order_date",
            "ship_date",
            "order_priority",
            "order_quantity",
            "sales",
            "discount",
            "profit",
            "unit_price",
            "shipping_cost",
            "customer_name",
            "customer_segment",
            "region",
            "province",
            "ship_mode",
            "product_category",
            "product_sub_category",
            "product_name",
            "product_container",
            "product_base_margin",
        ]
        ordered = [column for column in preferred_order if column in dataframe.columns]
        remaining = [column for column in dataframe.columns if column not in ordered]
        return dataframe[ordered + remaining]


def main() -> None:
    """Run data cleaning as a command-line script."""
    cleaner = RetailDataCleaner()
    _, summary = cleaner.run()

    print("Data cleaning completed.")
    print(f"Rows before cleaning: {summary.rows_before:,}")
    print(f"Rows after cleaning: {summary.rows_after:,}")
    print(f"Duplicates removed: {summary.duplicates_removed:,}")
    print(f"Cleaned CSV: {summary.cleaned_csv_path}")
    print(f"Cleaned Excel: {summary.cleaned_excel_path}")


if __name__ == "__main__":
    main()
