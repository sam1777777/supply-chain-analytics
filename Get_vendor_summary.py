
import os
import logging
import sqlite3
import pandas as pd

from ingestion_db import engine, ingest_db

# --------------------------------------------------
# 1. Logging configuration
# --------------------------------------------------

os.makedirs("logs", exist_ok=True)

logging.basicConfig(
    filename=os.path.join("logs", "get_vendor_summary.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    force=True
)


# --------------------------------------------------
# 2. Create vendor summary using SQL
# --------------------------------------------------

def create_vendor_summary(conn):
    """Combine purchasing, sales and freight data."""

    query = """
    WITH FreightSummary AS (
        SELECT
            VendorNumber,
            SUM(Freight) AS FreightCost
        FROM vendor_invoice
        GROUP BY VendorNumber
    ),

    PurchaseSummary AS (
        SELECT
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.PurchasePrice,
            pp.Price AS ActualPrice,
            pp.Volume,
            SUM(p.Quantity) AS TotalPurchaseQuantity,
            SUM(p.Dollars) AS TotalPurchaseDollars
        FROM purchase p
        JOIN purchase_price pp
            ON p.Brand = pp.Brand
        WHERE p.PurchasePrice > 0
        GROUP BY
            p.VendorNumber,
            p.VendorName,
            p.Brand,
            p.Description,
            p.PurchasePrice,
            pp.Price,
            pp.Volume
    ),

    SalesSummary AS (
        SELECT
            VendorNo,
            Brand,
            SUM(SalesQuantity) AS TotalSalesQuantity,
            SUM(SalesDollars) AS TotalSalesDollars,
            SUM(SalesPrice) AS TotalSalesPrice,
            SUM(ExciseTax) AS TotalExciseTax
        FROM sales
        GROUP BY VendorNo, Brand
    )

    SELECT
        ps.VendorNumber,
        ps.VendorName,
        ps.Brand,
        ps.Description,
        ps.PurchasePrice,
        ps.ActualPrice,
        ps.Volume,
        ps.TotalPurchaseQuantity,
        ps.TotalPurchaseDollars,
        ss.TotalSalesQuantity,
        ss.TotalSalesDollars,
        ss.TotalSalesPrice,
        ss.TotalExciseTax,
        fs.FreightCost
    FROM PurchaseSummary ps
    LEFT JOIN SalesSummary ss
        ON ps.VendorNumber = ss.VendorNo
        AND ps.Brand = ss.Brand
    LEFT JOIN FreightSummary fs
        ON ps.VendorNumber = fs.VendorNumber
    ORDER BY ps.TotalPurchaseDollars DESC
    """

    vendor_sales_summary = pd.read_sql_query(query, conn)

    return vendor_sales_summary


# --------------------------------------------------
# 3. Clean data and create analysis columns
# --------------------------------------------------

def clean_data(df):
    """Clean the summary DataFrame and calculate metrics."""

    df = df.copy()

    # Convert numeric columns safely
    numeric_columns = [
        "Volume",
        "PurchasePrice",
        "ActualPrice",
        "TotalPurchaseQuantity",
        "TotalPurchaseDollars",
        "TotalSalesQuantity",
        "TotalSalesDollars",
        "TotalSalesPrice",
        "TotalExciseTax",
        "FreightCost"
    ]

    for column in numeric_columns:
        df[column] = pd.to_numeric(
            df[column], errors="coerce"
        )

    # Clean text columns
    for column in ["VendorName", "Description"]:
        df[column] = df[column].fillna("").astype(str).str.strip()

    # Fill missing numeric values
    df[numeric_columns] = df[numeric_columns].fillna(0)

    # Calculate analysis metrics
    df["GrossProfit"] = (
        df["TotalSalesDollars"] - df["TotalPurchaseDollars"]
    )

    df["ProfitMargin"] = (
        df["GrossProfit"]
        .div(df["TotalSalesDollars"].replace(0, float("nan")))
        * 100
    )

    df["StockTurnover"] = (
        df["TotalSalesQuantity"]
        .div(df["TotalPurchaseQuantity"].replace(0, float("nan")))
        * 100
    )

    df["SalesToPurchaseRatio"] = (
        df["TotalSalesDollars"]
        .div(df["TotalPurchaseDollars"].replace(0, float("nan")))
        * 100
    )

    return df


# --------------------------------------------------
# 4. Run the complete workflow
# --------------------------------------------------

if __name__ == "__main__":

    conn = sqlite3.connect("inventory.db")

    try:
        logging.info("Creating vendor summary table...")

        summary_df = create_vendor_summary(conn)

        logging.info(
            "Vendor summary created: %s",
            summary_df.shape
        )

        logging.info("Cleaning data...")

        clean_df = clean_data(summary_df)

        logging.info(
            "Data cleaning completed: %s",
            clean_df.shape
        )

        logging.info("Ingesting data...")

        ingest_db(
            clean_df,
            "vendor_sales_summary",
            engine
        )

        logging.info(
            "Vendor summary process completed successfully."
        )

        print("Vendor summary created successfully!")
        print("Summary shape:", clean_df.shape)
        display(clean_df.head())

    except Exception:
        logging.exception("Vendor summary process failed.")
        raise

    finally:
        conn.close()
