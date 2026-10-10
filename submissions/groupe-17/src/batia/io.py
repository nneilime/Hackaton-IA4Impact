import pandas as pd
from batia.config import OUT


def save_table(df: pd.DataFrame, name: str) -> None:
    """Parquet si pyarrow est installé, sinon CSV (même nom)."""
    try:
        df.to_parquet(OUT / f"{name}.parquet", index=False)
    except ImportError:
        df.to_csv(OUT / f"{name}.csv", index=False)


def read_table(name: str) -> pd.DataFrame:
    p = OUT / f"{name}.parquet"
    if p.exists():
        return pd.read_parquet(p)
    return pd.read_csv(OUT / f"{name}.csv")
