from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "scientific_production.db"
SUMMARY_PATH = BASE_DIR / "artifacts" / "analysis_summary.json"
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


st.set_page_config(page_title="Producao Cientifica em Ciencias Sociais", layout="wide")


@st.cache_data
def load_data() -> pd.DataFrame:
    with sqlite3.connect(DB_PATH) as conn:
        return pd.read_sql_query("SELECT * FROM vw_journal_analysis", conn)


@st.cache_data
def load_summary() -> dict:
    if not SUMMARY_PATH.exists():
        return {}
    return json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))


def apply_filters(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros")
    qualis = st.sidebar.multiselect("QUALIS", QUALIS_ORDER, default=QUALIS_ORDER)
    country_group = st.sidebar.multiselect(
        "Origem do periodico",
        ["Brazil", "International", "Unmatched"],
        default=["Brazil", "International", "Unmatched"],
    )
    regions = sorted(df["region"].dropna().unique().tolist())
    selected_regions = st.sidebar.multiselect("Regiao", regions, default=regions)

    years = df["coverage_end_year"].dropna()
    year_range = None
    if not years.empty:
        year_range = st.sidebar.slider(
            "Ano final de cobertura SCImago",
            min_value=int(years.min()),
            max_value=int(years.max()),
            value=(int(years.min()), int(years.max())),
        )

    filtered = df[df["qualis"].isin(qualis) & df["country_group"].isin(country_group)].copy()
    if selected_regions:
        filtered = filtered[filtered["region"].isin(selected_regions) | filtered["region"].isna()]
    if year_range:
        filtered = filtered[
            filtered["coverage_end_year"].isna()
            | filtered["coverage_end_year"].between(year_range[0], year_range[1])
        ]
    return filtered


def metric_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div style="padding:1rem 1.2rem;border:1px solid #d9d9d9;border-radius:16px;background:#fff8ed;">
            <div style="font-size:0.85rem;color:#6c584c;text-transform:uppercase;letter-spacing:0.08em;">{label}</div>
            <div style="font-size:2rem;font-weight:700;color:#283618;">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def main() -> None:
    df = load_data()
    summary = load_summary()
    filtered = apply_filters(df)
    matched = filtered[filtered["country"].notna()].copy()
    journal_level = (
        matched.sort_values(["source_id", "avg_citations"], ascending=[True, False])
        .drop_duplicates(subset=["source_id"])
    )

    st.title("Analise de Producao Cientifica em Ciencias Sociais")
    st.caption("Base unificada a partir de QUALIS/FI do programa e metadados SCImago.")

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        metric_card("Total de registros do programa", f"{len(filtered):,}".replace(",", "."))
    with c2:
        metric_card("Media de citacoes", f"{filtered['avg_citations'].mean():.2f}" if not filtered.empty else "0")
    with c3:
        pct_q1 = (journal_level["best_quartile"].eq("Q1").mean() * 100) if not journal_level.empty else 0
        metric_card("% de periodicos Q1", f"{pct_q1:.1f}%")
    with c4:
        coverage = (matched.shape[0] / filtered.shape[0] * 100) if not filtered.empty else 0
        metric_card("Cobertura SCImago", f"{coverage:.1f}%")

    st.markdown("### Principais achados")
    for insight in summary.get("insights", []):
        st.write(f"- {insight}")

    chart_col, table_col = st.columns([1.25, 1])

    qualis_dist = (
        filtered.groupby(["qualis"])
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
    fig_bar.update_layout(showlegend=False, plot_bgcolor="#faf7f2", paper_bgcolor="#faf7f2")
    chart_col.plotly_chart(fig_bar, use_container_width=True)

    top5 = (
        journal_level.sort_values(["scimago_sjr", "avg_citations"], ascending=[False, False])
        .loc[:, ["journal_name", "country", "best_quartile", "scimago_sjr", "scimago_h_index", "qualis"]]
        .head(5)
        .rename(
            columns={
                "journal_name": "Periodico",
                "country": "Pais",
                "best_quartile": "Quartil",
                "scimago_sjr": "SJR",
                "scimago_h_index": "Indice H",
                "qualis": "QUALIS",
            }
        )
    )
    table_col.markdown("### Top 5 periodicos por SJR")
    table_col.dataframe(top5, use_container_width=True, hide_index=True)

    st.markdown("### Impacto vs. volume")
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
    fig_scatter.update_layout(plot_bgcolor="#ffffff", paper_bgcolor="#ffffff")
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.markdown("### Benchmarking internacional")
    benchmark = (
        journal_level.groupby("country_group")
        .agg(
            Periodicos=("source_id", "count"),
            SJR_medio=("scimago_sjr", "mean"),
            Percentual_Q1=("best_quartile", lambda x: (x == "Q1").mean() * 100),
            H_index_mediano=("scimago_h_index", "median"),
            Citacoes_medias=("avg_citations", "mean"),
        )
        .reset_index()
    )
    st.dataframe(benchmark.round(2), use_container_width=True, hide_index=True)

    benchmark_chart = px.bar(
        benchmark,
        x="country_group",
        y=["SJR_medio", "Percentual_Q1", "H_index_mediano"],
        barmode="group",
        title="Brasil vs. internacional: intensidade bibliometrica",
        labels={"value": "Valor", "country_group": "Grupo"},
    )
    st.plotly_chart(benchmark_chart, use_container_width=True)

    quartile_dist = (
        journal_level.groupby(["country_group", "best_quartile"])
        .size()
        .reset_index(name="Periodicos")
        .sort_values(["country_group", "best_quartile"])
    )
    quartile_chart = px.bar(
        quartile_dist,
        x="best_quartile",
        y="Periodicos",
        color="country_group",
        barmode="group",
        title="Distribuicao de quartis: Brasil vs. internacional",
        labels={
            "best_quartile": "Quartil",
            "Periodicos": "Quantidade de periodicos",
            "country_group": "Grupo",
        },
    )
    st.plotly_chart(quartile_chart, use_container_width=True)

    st.markdown("### Drill-down por pais/regiao")
    detail = matched.loc[
        :,
        ["journal_name", "qualis", "country", "region", "best_quartile", "scimago_sjr", "scimago_h_index", "avg_citations"],
    ]
    detail = detail.sort_values(["country", "scimago_sjr"], ascending=[True, False])
    st.dataframe(detail.round(2), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
