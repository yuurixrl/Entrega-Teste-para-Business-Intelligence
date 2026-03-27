from __future__ import annotations

import argparse
import re
import sqlite3
import unicodedata
from pathlib import Path

import pandas as pd


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "scientific_production.db"
QUALIS_ORDER = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C", "NP"]


def ensure_dirs() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RAW_DIR.mkdir(parents=True, exist_ok=True)


def parse_decimal(value: object) -> float | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    if not text:
        return None
    return float(text.replace(".", "").replace(",", "."))


def parse_int(value: object) -> int | None:
    if pd.isna(value):
        return None
    text = re.sub(r"[^\d]", "", str(value))
    return int(text) if text else None


def normalize_issn(value: object) -> str | None:
    if pd.isna(value):
        return None
    cleaned = re.sub(r"[^0-9X]", "", str(value).upper())
    return cleaned or None


def normalize_column_name(column: str) -> str:
    ascii_column = unicodedata.normalize("NFKD", column).encode("ascii", "ignore").decode("ascii")
    ascii_column = ascii_column.lower().strip()
    ascii_column = re.sub(r"[^a-z0-9]+", "_", ascii_column)
    return ascii_column.strip("_")


def split_issn_list(value: object) -> list[str]:
    if pd.isna(value):
        return []
    result = []
    for item in str(value).split(","):
        cleaned = normalize_issn(item)
        if cleaned:
            result.append(cleaned)
    return result


def extract_coverage_years(value: object) -> tuple[int | None, int | None]:
    if pd.isna(value):
        return None, None
    years = [int(year) for year in re.findall(r"\b(?:19|20)\d{2}\b", str(value))]
    if not years:
        return None, None
    return min(years), max(years)


def resolve_input_path(explicit_path: str | None, filename: str) -> Path:
    candidates = []
    if explicit_path:
        candidates.append(Path(explicit_path))
    candidates.append(RAW_DIR / filename)
    candidates.append(Path.home() / "Downloads" / filename)

    for candidate in candidates:
        if candidate.exists():
            return candidate

    searched = "\n".join(f"- {path}" for path in candidates)
    raise FileNotFoundError(
        f"Input file '{filename}' not found. Checked:\n{searched}\n"
        "Provide --fi1/--fi2 explicitly or place the CSVs under data/raw/."
    )


def load_fi1(fi1_path: Path) -> pd.DataFrame:
    df = pd.read_csv(fi1_path, dtype={"ISSN": str})
    df = df.rename(columns={column: normalize_column_name(column) for column in df.columns})
    df = df.rename(
        columns={
            "periodico": "journal_name",
            "h_index": "h_index_fi1",
            "citacoes_2019_2021": "citations_2019_2021",
            "citacoes_media": "avg_citations",
        }
    )
    df["issn"] = df["issn"].str.strip()
    df["issn_norm"] = df["issn"].apply(normalize_issn)
    df["qualis"] = df["qualis"].fillna("NP").str.strip().str.upper()
    df["qualis_rank"] = df["qualis"].apply(lambda x: QUALIS_ORDER.index(x) + 1 if x in QUALIS_ORDER else len(QUALIS_ORDER) + 1)
    df["fi_sjr"] = df["fi_sjr"].apply(parse_decimal)
    df["h_index_fi1"] = df["h_index_fi1"].apply(parse_int)
    df["citations_2019_2021"] = df["citations_2019_2021"].apply(parse_int)
    df["avg_citations"] = df["avg_citations"].apply(parse_decimal)
    return df


def load_fi2(fi2_path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    df = pd.read_csv(fi2_path, dtype={"Issn": str})
    df = df.rename(columns={column: normalize_column_name(column) for column in df.columns})
    df = df.rename(
        columns={
            "sourceid": "source_id",
            "issn": "issn_raw",
            "sjr_best_quartile": "best_quartile",
            "cites_doc_2years": "cites_per_doc_2years",
            "ref_doc": "refs_per_doc",
        }
    )
    for column in ["sjr", "cites_per_doc_2years", "refs_per_doc"]:
        df[column] = df[column].apply(parse_decimal)
    for column in ["rank", "source_id", "h_index", "total_docs_2022", "total_docs_3years", "total_refs", "total_cites_3years", "citable_docs_3years"]:
        df[column] = df[column].apply(parse_int)
    coverage_years = df["coverage"].apply(extract_coverage_years)
    df["coverage_start_year"] = coverage_years.apply(lambda x: x[0])
    df["coverage_end_year"] = coverage_years.apply(lambda x: x[1])
    issn_map = df[["source_id", "title", "country", "region", "best_quartile", "issn_raw"]].copy()
    issn_map["issn_norm"] = issn_map["issn_raw"].apply(split_issn_list)
    issn_map = (
        issn_map.explode("issn_norm")
        .dropna(subset=["issn_norm"])
        .drop_duplicates(subset=["source_id", "issn_norm"])
    )
    return df, issn_map


def persist_to_sqlite(fi1: pd.DataFrame, fi2: pd.DataFrame, fi2_issn: pd.DataFrame) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            DROP VIEW IF EXISTS vw_kpis;
            DROP VIEW IF EXISTS vw_journal_analysis;
            DROP TABLE IF EXISTS fi1_articles;
            DROP TABLE IF EXISTS fi2_journals;
            DROP TABLE IF EXISTS fi2_journal_issn;
            """
        )
        fi1.to_sql("fi1_articles", conn, if_exists="replace", index=False)
        fi2.to_sql("fi2_journals", conn, if_exists="replace", index=False)
        fi2_issn.to_sql("fi2_journal_issn", conn, if_exists="replace", index=False)

        conn.executescript(
            """
            DROP VIEW IF EXISTS vw_journal_analysis;
            CREATE VIEW vw_journal_analysis AS
            SELECT
                a.issn,
                a.issn_norm,
                a.journal_name,
                a.qualis,
                a.qualis_rank,
                a.fi_sjr AS program_sjr,
                a.h_index_fi1 AS program_h_index,
                a.citations_2019_2021,
                a.avg_citations,
                b.source_id,
                b.title AS scimago_title,
                b.type AS scimago_type,
                b.sjr AS scimago_sjr,
                b.best_quartile,
                b.h_index AS scimago_h_index,
                b.total_docs_2022,
                b.total_docs_3years,
                b.total_cites_3years,
                b.cites_per_doc_2years,
                b.country,
                b.region,
                b.publisher,
                b.coverage,
                b.coverage_start_year,
                b.coverage_end_year,
                b.categories,
                b.areas,
                CASE
                    WHEN b.country = 'Brazil' THEN 'Brazil'
                    WHEN b.country IS NULL THEN 'Unmatched'
                    ELSE 'International'
                END AS country_group
            FROM fi1_articles a
            LEFT JOIN fi2_journal_issn m
                ON a.issn_norm = m.issn_norm
            LEFT JOIN fi2_journals b
                ON m.source_id = b.source_id;

            DROP VIEW IF EXISTS vw_kpis;
            CREATE VIEW vw_kpis AS
            SELECT
                COUNT(*) AS total_articles,
                ROUND(AVG(avg_citations), 2) AS avg_citations,
                ROUND(AVG(citations_2019_2021), 2) AS avg_total_citations_2019_2021,
                ROUND(100.0 * AVG(CASE WHEN best_quartile = 'Q1' THEN 1 ELSE 0 END), 2) AS pct_q1,
                ROUND(100.0 * AVG(CASE WHEN country = 'Brazil' THEN 1 ELSE 0 END), 2) AS pct_brazilian,
                ROUND(100.0 * AVG(CASE WHEN country IS NOT NULL THEN 1 ELSE 0 END), 2) AS pct_matched_scimago
            FROM vw_journal_analysis;
            """
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load CSV datasets into SQLite for dashboard analysis.")
    parser.add_argument("--fi1", help="Path to artigos_fi1.csv")
    parser.add_argument("--fi2", help="Path to artigos_fi2.csv")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_dirs()
    fi1_path = resolve_input_path(args.fi1, "artigos_fi1.csv")
    fi2_path = resolve_input_path(args.fi2, "artigos_fi2.csv")
    fi1 = load_fi1(fi1_path)
    fi2, fi2_issn = load_fi2(fi2_path)
    persist_to_sqlite(fi1, fi2, fi2_issn)
    print(f"SQLite database created at: {DB_PATH}")
    print(f"fi1 source: {fi1_path}")
    print(f"fi2 source: {fi2_path}")
    print(f"fi1_articles rows: {len(fi1)}")
    print(f"fi2_journals rows: {len(fi2)}")
    print(f"fi2_journal_issn rows: {len(fi2_issn)}")


if __name__ == "__main__":
    main()
