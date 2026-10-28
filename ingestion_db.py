
import pandas as pd
import os
import logging
from sqlalchemy import create_engine


# Database connection
engine = create_engine("sqlite:///inventory.db")


# Create logs folder
os.makedirs("logs", exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=os.path.join("logs", "project.log"),
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def ingest_db(df, table_name, engine):
    """Save a DataFrame to a database table."""

    df.to_sql(
        table_name,
        con=engine,
        if_exists="replace",
        index=False
    )

    logging.info("Inserted %s into database", table_name)


def load_raw_data():
    """Load CSV files from the current working directory into SQLite."""

    for file in os.listdir():
        if file.lower().endswith(".csv"):
            try:
                df = pd.read_csv(file)
                logging.info("Loaded %s with shape %s", file, df.shape)

                ingest_db(df, file[:-4], engine)

                logging.info("Inserted %s into database", file)

            except Exception:
                logging.exception("Failed to process %s", file)
                raise
