from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px


BASE_DIR = Path(__file__).resolve().parents[1]
DB_PATH = BASE_DIR / "data" / "scientific_production.db"
SUMMARY_PATH = BASE_DIR / "artifacts" / "analysis_summary.json"
EXPORT_DIR = BASE_DIR / "artifacts" / "dashboard_assets"
QUALIS_ORDER = ["A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4", "C", "NP"]
QUALIS_COLOR_MAP = {
    "A1": "#003049",
    "A2": "#1d3557",
    "A3": "#457b9d",
    "A4": "#6d9dc5",
    "B1": "#d62828",
    "B2": "#e76f51",
    "B3": "#f4a261",
    "B4": "#f6bd60",
    "C": "#9c6644",
    "NP": "#adb5bd",
}


def load_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM vw_journal_analysis", conn)


def export_figure(fig, filename: str) -> None:
    fig.write_html(str(EXPORT_DIR / f"{filename}.html"), include_plotlyjs="cdn")
    fig.write_image(str(EXPORT_DIR / f"{filename}.png"), width=1400, height=850, scale=2)


def main() -> None:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_data()
    matched = df[df["country"].notna()].copy()
    journal_level = (
        matched.sort_values(["source_id", "avg_citations"], ascending=[True, False])
        .drop_duplicates(subset=["source_id"])
    )

    qualis_dist = (
        df.groupby(["qualis"])
        .size()
        .reindex(QUALIS_ORDER, fill_value=0)
        .reset_index(name="articles")
    )
    fig_bar = px.bar(
        qualis_dist,
        x="qualis",
        y="articles",
        color="qualis",
        color_discrete_map=QUALIS_COLOR_MAP,
        title="Distribuicao QUALIS",
        labels={"qualis": "Estrato QUALIS", "articles": "Quantidade"},
    )
    export_figure(fig_bar, "qualis_distribution")

    fig_scatter = px.scatter(
        matched,
        x="scimago_sjr",
        y="avg_citations",
        color="qualis",
        size="citations_2019_2021",
        hover_data=["journal_name", "country", "best_quartile"],
        color_discrete_map=QUALIS_COLOR_MAP,
        title="SJR vs. media de citacoes",
        labels={
            "scimago_sjr": "SJR (SCImago)",
            "avg_citations": "Citacoes medias",
            "citations_2019_2021": "Citacoes 2019-2021",
        },
    )
    export_figure(fig_scatter, "sjr_vs_citations")

    quartile_dist = (
        journal_level.groupby(["country_group", "best_quartile"])
        .size()
        .reset_index(name="journals")
        .sort_values(["country_group", "best_quartile"])
    )
    quartile_chart = px.bar(
        quartile_dist,
        x="best_quartile",
        y="journals",
        color="country_group",
        barmode="group",
        title="Distribuicao de quartis: Brasil vs. internacional",
        labels={
            "best_quartile": "Quartil",
            "journals": "Quantidade de periodicos",
            "country_group": "Grupo",
        },
    )
    export_figure(quartile_chart, "quartile_benchmark")

    top5 = (
        journal_level.sort_values(["scimago_sjr", "avg_citations"], ascending=[False, False])
        .loc[:, ["journal_name", "country", "best_quartile", "scimago_sjr", "scimago_h_index", "qualis"]]
        .head(5)
    )
    (EXPORT_DIR / "top5_sjr.csv").write_text(top5.to_csv(index=False), encoding="utf-8")
    (EXPORT_DIR / "summary_snapshot.json").write_text(SUMMARY_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Assets exported to: {EXPORT_DIR}")


if __name__ == "__main__":
    main()
