from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
from scipy.stats import spearmanr


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "scientific_production.db"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
SUMMARY_PATH = ARTIFACTS_DIR / "analysis_summary.json"


def load_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM vw_journal_analysis", conn)


def safe_round(value: float | None, digits: int = 2) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def build_summary(df: pd.DataFrame) -> dict:
    full_program = df.copy()
    full_program["qualis_num"] = full_program["qualis_rank"].astype(float)

    matched = df[df["country"].notna()].copy()
    journal_level = (
        matched.sort_values(["source_id", "avg_citations"], ascending=[True, False])
        .drop_duplicates(subset=["source_id"])
    )

    corr_qualis = spearmanr(full_program["qualis_num"], full_program["avg_citations"], nan_policy="omit")
    corr_sjr = spearmanr(matched["scimago_sjr"], matched["avg_citations"], nan_policy="omit")

    country_benchmark = (
        journal_level.groupby("country_group")
        .agg(
            journals=("source_id", "count"),
            avg_sjr=("scimago_sjr", "mean"),
            median_h_index=("scimago_h_index", "median"),
            pct_q1=("best_quartile", lambda x: (x == "Q1").mean() * 100),
            avg_citations=("avg_citations", "mean"),
        )
        .reset_index()
    )

    quartile_distribution = (
        journal_level.groupby(["country_group", "best_quartile"])
        .size()
        .reset_index(name="journals")
        .sort_values(["country_group", "best_quartile"])
    )

    top_sjr = (
        journal_level.sort_values(["scimago_sjr", "avg_citations"], ascending=[False, False])
        .loc[:, ["journal_name", "country", "best_quartile", "scimago_sjr", "scimago_h_index", "avg_citations", "qualis"]]
        .head(5)
    )

    qualis_distribution = (
        df.groupby(["qualis", "qualis_rank"])
        .size()
        .reset_index(name="articles")
        .sort_values("qualis_rank")
    )

    summary = {
        "rows_total": int(len(df)),
        "rows_matched_scimago": int(len(matched)),
        "rows_unique_journals_matched": int(len(journal_level)),
        "match_rate_pct": safe_round((len(matched) / len(df)) * 100),
        "correlations": {
            "qualis_rank_vs_avg_citations_spearman": safe_round(corr_qualis.statistic),
            "qualis_rank_vs_avg_citations_pvalue": safe_round(corr_qualis.pvalue, 4),
            "scimago_sjr_vs_avg_citations_spearman": safe_round(corr_sjr.statistic),
            "scimago_sjr_vs_avg_citations_pvalue": safe_round(corr_sjr.pvalue, 4),
        },
        "country_benchmark": country_benchmark.round(2).to_dict(orient="records"),
        "quartile_distribution": quartile_distribution.to_dict(orient="records"),
        "top_sjr": top_sjr.round(2).to_dict(orient="records"),
        "qualis_distribution": qualis_distribution.to_dict(orient="records"),
        "insights": [
            f"A base do programa tem {len(df):,} registros classificados; {len(matched):,} ({safe_round((len(matched) / len(df)) * 100)}%) encontraram correspondencia direta no SCImago por ISSN.".replace(",", "."),
            f"A correlacao de Spearman entre QUALIS e media de citacoes na base completa foi {safe_round(corr_qualis.statistic)}, sugerindo relacao {'moderada' if abs(corr_qualis.statistic or 0) >= 0.3 else 'fraca'} entre estrato e citacao media.",
            f"A correlacao entre SJR e media de citacoes foi {safe_round(corr_sjr.statistic)}, indicando que periodicos mais influentes no SCImago tendem a concentrar mais citacoes no conjunto casado.",
        ],
    }
    return summary


def main() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    summary = build_summary(df)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Summary written to: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
