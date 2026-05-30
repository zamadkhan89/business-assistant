"""Dataset Analysis Templates — comprehensive EDA, profiling, distributions, outliers, correlations, time trends."""
import asyncio
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.auth import get_current_user
from app.core.db import get_db
from app.data.duckdb_connector import get_conn
from app.models.user import User

router = APIRouter(prefix="/analysis", tags=["analysis"])

TEMPLATES = {
    "profiling": {
        "name": "Full Profiling Report",
        "description": "Shape, types, nulls, per-column stats (mean/median/std/quartiles/skew), top values, correlations, and outlier flags.",
        "icon": "clipboard-list",
        "color": "blue",
    },
    "distribution": {
        "name": "Distributions",
        "description": "Min, max, mean, median, std dev for numeric columns. Top-10 values for text columns.",
        "icon": "bar-chart-2",
        "color": "violet",
    },
    "outliers": {
        "name": "Outlier Detection",
        "description": "IQR method: flags rows where numeric columns fall outside the expected range.",
        "icon": "alert-triangle",
        "color": "amber",
    },
    "correlation": {
        "name": "Correlations",
        "description": "Pearson correlation coefficients between all pairs of numeric columns.",
        "icon": "git-branch",
        "color": "emerald",
    },
    "time_trends": {
        "name": "Time Trends",
        "description": "Monthly aggregations of numeric columns grouped by a detected date column.",
        "icon": "trending-up",
        "color": "rose",
    },
}


class AnalysisRequest(BaseModel):
    table_name: str
    template: str


class RunAllRequest(BaseModel):
    table_name: str


def _is_numeric(dtype: str) -> bool:
    return any(t in dtype.upper() for t in ["INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL", "BIGINT", "HUGEINT"])


def _is_date(dtype: str) -> bool:
    return any(t in dtype.upper() for t in ["DATE", "TIMESTAMP", "DATETIME"])


def _is_text(dtype: str) -> bool:
    return any(t in dtype.upper() for t in ["VARCHAR", "TEXT", "CHAR", "STRING"])


# ── Full Profiling ────────────────────────────────────────────────────────────

def _run_profiling(table_name: str) -> list[dict]:
    sections: list[dict] = []

    with get_conn() as conn:
        row_count = conn.execute(f'SELECT COUNT(*) FROM "{table_name}"').fetchone()[0]
        schema = conn.execute(f'DESCRIBE "{table_name}"').fetchdf()
        summary_df = conn.execute(f'SUMMARIZE "{table_name}"').fetchdf()

        col_count = len(schema)
        numeric_cols = [r["column_name"] for _, r in schema.iterrows() if _is_numeric(r["column_type"])]
        text_cols    = [r["column_name"] for _, r in schema.iterrows() if _is_text(r["column_type"])]
        date_cols    = [r["column_name"] for _, r in schema.iterrows() if _is_date(r["column_type"])]

        # Duplicate count
        try:
            dup_count = int(row_count - conn.execute(f'SELECT COUNT(*) FROM (SELECT DISTINCT * FROM "{table_name}")').fetchone()[0])
        except Exception:
            dup_count = "n/a"

        # Null summary from SUMMARIZE
        try:
            null_series = summary_df["null_percentage"].astype(float)
            cols_with_nulls = int((null_series > 0).sum())
            total_null_pct  = round(float(null_series.mean()), 1)
        except Exception:
            cols_with_nulls = "n/a"
            total_null_pct  = "n/a"

        sections.append({
            "title": "Dataset Overview",
            "type": "stats",
            "stats": {
                "Rows": f"{row_count:,}",
                "Columns": str(col_count),
                "Numeric columns": str(len(numeric_cols)),
                "Text columns": str(len(text_cols)),
                "Date columns": str(len(date_cols)),
                "Duplicate rows": str(dup_count),
                "Columns with nulls": str(cols_with_nulls),
                "Avg null rate": f"{total_null_pct}%",
            },
        })

        # Column type breakdown chart
        type_counts = {"Numeric": len(numeric_cols), "Text": len(text_cols), "Date": len(date_cols),
                       "Other": col_count - len(numeric_cols) - len(text_cols) - len(date_cols)}
        type_counts = {k: v for k, v in type_counts.items() if v > 0}
        if type_counts:
            fig = px.pie(names=list(type_counts.keys()), values=list(type_counts.values()),
                         title="Column Type Distribution", hole=0.4,
                         color_discrete_sequence=px.colors.qualitative.Pastel)
            sections.append({"title": "Column Types", "type": "chart", "chart_json": fig.to_json()})

        # Column-level summary table
        display_cols = ["column_name", "column_type", "min", "max", "approx_unique", "null_percentage"]
        available = [c for c in display_cols if c in summary_df.columns]
        if available:
            tbl = (summary_df[available]
                   .rename(columns={"column_name": "Column", "column_type": "Type",
                                    "null_percentage": "Null %", "approx_unique": "Unique"})
                   .to_dict(orient="records"))
            sections.append({"title": "Column Summary", "type": "table",
                              "description": "Types, value ranges, approximate unique counts, null rates.", "data": tbl})

        # Null rate bar chart
        if "null_percentage" in summary_df.columns and "column_name" in summary_df.columns:
            null_df = summary_df[["column_name", "null_percentage"]].copy()
            null_df["null_percentage"] = null_df["null_percentage"].astype(float)
            null_df = null_df[null_df["null_percentage"] > 0].sort_values("null_percentage", ascending=False)
            if not null_df.empty:
                fig = px.bar(null_df, x="column_name", y="null_percentage",
                             title="Null Rate per Column (%)", color="null_percentage",
                             color_continuous_scale="Reds", labels={"column_name": "Column", "null_percentage": "Null %"})
                sections.append({"title": "Null Rates", "type": "chart", "chart_json": fig.to_json()})

        # Numeric column deep stats
        if numeric_cols:
            stat_rows = []
            for col in numeric_cols[:12]:
                try:
                    r = conn.execute(f"""
                        SELECT
                            '{col}'::VARCHAR                              AS "Column",
                            ROUND(MIN("{col}")::DOUBLE, 4)::VARCHAR       AS "Min",
                            ROUND(MAX("{col}")::DOUBLE, 4)::VARCHAR       AS "Max",
                            ROUND(AVG("{col}")::DOUBLE, 4)::VARCHAR       AS "Mean",
                            ROUND(MEDIAN("{col}")::DOUBLE, 4)::VARCHAR    AS "Median",
                            ROUND(STDDEV("{col}")::DOUBLE, 4)::VARCHAR    AS "Std Dev",
                            ROUND(PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "{col}")::DOUBLE, 4)::VARCHAR AS "Q1",
                            ROUND(PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "{col}")::DOUBLE, 4)::VARCHAR AS "Q3",
                            ROUND(SKEWNESS("{col}")::DOUBLE, 4)::VARCHAR  AS "Skewness",
                            (COUNT(*) - COUNT("{col}"))::VARCHAR          AS "Nulls"
                        FROM "{table_name}"
                    """).fetchdf().to_dict(orient="records")[0]
                    stat_rows.append(r)
                except Exception:
                    pass

            if stat_rows:
                sections.append({
                    "title": "Numeric Column Statistics",
                    "type": "table",
                    "description": "Full distribution stats including quartiles and skewness.",
                    "data": stat_rows,
                })

                # Skewness chart (values far from 0 = skewed distribution)
                skew_df = pd.DataFrame([{"Column": r["Column"], "Skewness": float(r["Skewness"] or 0)} for r in stat_rows])
                if not skew_df.empty:
                    fig = px.bar(skew_df, x="Column", y="Skewness", title="Skewness per Numeric Column",
                                 color="Skewness", color_continuous_scale="RdBu",
                                 color_continuous_midpoint=0)
                    sections.append({"title": "Skewness", "type": "chart",
                                     "description": "0 = symmetric. Positive = right-skewed. Negative = left-skewed.",
                                     "chart_json": fig.to_json()})

                # Outlier flags per column (IQR × 1.5)
                outlier_rows = []
                for r in stat_rows:
                    col = r["Column"]
                    try:
                        q1 = float(r["Q1"] or 0)
                        q3 = float(r["Q3"] or 0)
                        iqr = q3 - q1
                        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
                        cnt = conn.execute(f"""
                            SELECT COUNT(*) FROM "{table_name}"
                            WHERE "{col}" < {lo} OR "{col}" > {hi}
                        """).fetchone()[0]
                        pct = round(100 * cnt / max(row_count, 1), 2)
                        outlier_rows.append({"Column": col, "Lower Fence": round(lo, 4),
                                             "Upper Fence": round(hi, 4),
                                             "Outliers": cnt, "Outlier %": f"{pct}%"})
                    except Exception:
                        pass
                if outlier_rows:
                    sections.append({"title": "Outlier Flags (IQR ×1.5)", "type": "table",
                                     "description": "Rows outside Q1−1.5×IQR … Q3+1.5×IQR.",
                                     "data": outlier_rows})

        # Categorical top values
        for col in text_cols[:5]:
            try:
                top = conn.execute(f"""
                    SELECT "{col}" AS value, COUNT(*) AS count,
                           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER(), 1) AS pct
                    FROM "{table_name}"
                    WHERE "{col}" IS NOT NULL
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
                """).fetchdf()
                if not top.empty:
                    fig = px.bar(top, x="value", y="count", title=f"{col} — Top 10 Values",
                                 text="pct", labels={"value": col, "count": "Count", "pct": "%"})
                    sections.append({"title": f"{col} (top 10)", "type": "chart", "chart_json": fig.to_json()})
            except Exception:
                pass

        # Correlation heatmap
        if len(numeric_cols) >= 2:
            try:
                cols_expr = ", ".join(f'"{c}"' for c in numeric_cols[:10])
                df_corr = conn.execute(f'SELECT {cols_expr} FROM "{table_name}"').fetchdf()
                corr_matrix = df_corr.corr(numeric_only=True).round(3)
                fig = go.Figure(go.Heatmap(
                    z=corr_matrix.values.tolist(),
                    x=corr_matrix.columns.tolist(),
                    y=corr_matrix.index.tolist(),
                    colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                    text=corr_matrix.values.round(2).tolist(),
                    texttemplate="%{text}",
                ))
                fig.update_layout(title="Correlation Heatmap")
                sections.append({"title": "Correlation Heatmap", "type": "chart", "chart_json": fig.to_json(),
                                  "description": "+1 = strong positive, −1 = strong negative, 0 = no linear relationship"})
            except Exception:
                pass

    return sections or [{"title": "No data", "type": "text", "text": "Could not profile this table."}]


# ── Distribution ──────────────────────────────────────────────────────────────

def _run_distribution(table_name: str) -> list[dict]:
    sections: list[dict] = []
    with get_conn() as conn:
        schema = conn.execute(f'DESCRIBE "{table_name}"').fetchdf()
        numeric_cols = [r["column_name"] for _, r in schema.iterrows() if _is_numeric(r["column_type"])][:8]
        text_cols    = [r["column_name"] for _, r in schema.iterrows() if _is_text(r["column_type"])][:5]

        if numeric_cols:
            stats_rows = []
            for col in numeric_cols:
                try:
                    s = conn.execute(f"""
                        SELECT
                            '{col}'::VARCHAR as "Column",
                            MIN("{col}")::VARCHAR as "Min",
                            MAX("{col}")::VARCHAR as "Max",
                            ROUND(AVG("{col}")::DOUBLE, 4)::VARCHAR as "Mean",
                            ROUND(MEDIAN("{col}")::DOUBLE, 4)::VARCHAR as "Median",
                            ROUND(STDDEV("{col}")::DOUBLE, 4)::VARCHAR as "Std Dev",
                            (COUNT(*) - COUNT("{col}"))::VARCHAR as "Nulls"
                        FROM "{table_name}"
                    """).fetchdf().to_dict(orient="records")[0]
                    stats_rows.append(s)
                except Exception:
                    pass

            if stats_rows:
                sections.append({"title": "Numeric Column Statistics", "type": "table", "data": stats_rows})
                means_df = pd.DataFrame([{"Column": r["Column"], "Mean": float(r["Mean"] or 0)} for r in stats_rows])
                fig = px.bar(means_df, x="Column", y="Mean", title="Mean Values by Column",
                             color="Mean", color_continuous_scale="Blues")
                sections.append({"title": "Mean Values", "type": "chart", "chart_json": fig.to_json()})

        for col in text_cols:
            try:
                top = conn.execute(f"""
                    SELECT "{col}" as value, COUNT(*) as count
                    FROM "{table_name}"
                    WHERE "{col}" IS NOT NULL
                    GROUP BY 1 ORDER BY 2 DESC LIMIT 10
                """).fetchdf()
                if not top.empty:
                    fig = px.bar(top, x="value", y="count", title=f"{col} — Top Values")
                    sections.append({"title": f"{col} (top 10 values)", "type": "chart", "chart_json": fig.to_json()})
            except Exception:
                pass

    return sections or [{"title": "No data", "type": "text", "text": "No numeric or text columns found."}]


# ── Outliers ──────────────────────────────────────────────────────────────────

def _run_outliers(table_name: str) -> list[dict]:
    with get_conn() as conn:
        schema = conn.execute(f'DESCRIBE "{table_name}"').fetchdf()
        numeric_cols = [r["column_name"] for _, r in schema.iterrows() if _is_numeric(r["column_type"])][:6]

        if not numeric_cols:
            return [{"title": "No Numeric Columns", "type": "text", "text": "This table has no numeric columns."}]

        rows = []
        for col in numeric_cols:
            try:
                result = conn.execute(f"""
                    WITH stats AS (
                        SELECT
                            PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY "{col}") AS q1,
                            PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY "{col}") AS q3
                        FROM "{table_name}" WHERE "{col}" IS NOT NULL
                    )
                    SELECT
                        '{col}'             AS "Column",
                        ROUND(stats.q1::DOUBLE, 2)                                  AS "Q1",
                        ROUND(stats.q3::DOUBLE, 2)                                  AS "Q3",
                        ROUND((stats.q1 - 1.5*(stats.q3-stats.q1))::DOUBLE, 2)     AS "Lower Fence",
                        ROUND((stats.q3 + 1.5*(stats.q3-stats.q1))::DOUBLE, 2)     AS "Upper Fence",
                        (SELECT COUNT(*) FROM "{table_name}"
                         WHERE "{col}" < stats.q1 - 1.5*(stats.q3-stats.q1)
                            OR "{col}" > stats.q3 + 1.5*(stats.q3-stats.q1))        AS "Outliers",
                        COUNT("{col}")                                               AS "Non-null Rows"
                    FROM "{table_name}", stats
                    WHERE "{col}" IS NOT NULL
                    GROUP BY stats.q1, stats.q3 LIMIT 1
                """).fetchdf()
                if not result.empty:
                    row = result.to_dict(orient="records")[0]
                    pct = round(100 * row["Outliers"] / max(row["Non-null Rows"], 1), 1)
                    row["Outlier %"] = f"{pct}%"
                    rows.append(row)
            except Exception:
                pass

    if not rows:
        return [{"title": "Could not compute", "type": "text", "text": "Outlier analysis failed for all numeric columns."}]

    fig = px.bar(
        pd.DataFrame([{"Column": r["Column"], "Outliers": r["Outliers"]} for r in rows]),
        x="Column", y="Outliers", title="Outlier Count per Column (IQR method)",
        color="Outliers", color_continuous_scale="Reds",
    )
    return [
        {"title": "Outlier Summary (IQR ×1.5)", "type": "table", "data": rows,
         "description": "Rows where value < Q1−1.5×IQR or > Q3+1.5×IQR"},
        {"title": "Outlier Counts", "type": "chart", "chart_json": fig.to_json()},
    ]


# ── Correlation ───────────────────────────────────────────────────────────────

def _run_correlation(table_name: str) -> list[dict]:
    with get_conn() as conn:
        schema = conn.execute(f'DESCRIBE "{table_name}"').fetchdf()
        numeric_cols = [r["column_name"] for _, r in schema.iterrows() if _is_numeric(r["column_type"])][:10]

        if len(numeric_cols) < 2:
            return [{"title": "Correlation", "type": "text",
                     "text": "Need at least 2 numeric columns for correlation analysis."}]

        # Full heatmap via pandas
        try:
            cols_expr = ", ".join(f'"{c}"' for c in numeric_cols)
            df = conn.execute(f'SELECT {cols_expr} FROM "{table_name}"').fetchdf()
            corr = df.corr(numeric_only=True).round(4)
            fig_heat = go.Figure(go.Heatmap(
                z=corr.values.tolist(), x=corr.columns.tolist(), y=corr.index.tolist(),
                colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                text=corr.values.round(2).tolist(), texttemplate="%{text}",
            ))
            fig_heat.update_layout(title="Correlation Heatmap")
        except Exception:
            fig_heat = None

        pairs = []
        for i, c1 in enumerate(numeric_cols):
            for c2 in numeric_cols[i + 1:]:
                try:
                    val = conn.execute(f'SELECT CORR("{c1}", "{c2}") FROM "{table_name}"').fetchone()[0]
                    pairs.append({
                        "Column A": c1, "Column B": c2,
                        "Correlation": round(float(val or 0), 4),
                        "Strength": (
                            "Strong" if abs(val or 0) >= 0.7
                            else "Moderate" if abs(val or 0) >= 0.4
                            else "Weak"
                        ),
                    })
                except Exception:
                    pass

    sections = []
    if fig_heat:
        sections.append({"title": "Correlation Heatmap", "type": "chart", "chart_json": fig_heat.to_json(),
                         "description": "+1 = strong positive, −1 = strong negative, 0 = no linear relationship"})
    if pairs:
        df_pairs = pd.DataFrame(pairs).sort_values("Correlation", key=abs, ascending=False)
        sections.append({"title": "Correlation Pairs", "type": "table", "data": df_pairs.to_dict(orient="records")})
        fig_bar = px.bar(df_pairs.head(20), x="Correlation", y="Column A", color="Correlation",
                         color_continuous_scale="RdBu", orientation="h",
                         title="Top Correlations (strongest first)", hover_data=["Column B", "Strength"])
        sections.append({"title": "Strongest Correlations", "type": "chart", "chart_json": fig_bar.to_json()})

    return sections or [{"title": "No pairs", "type": "text", "text": "Could not compute correlations."}]


# ── Time Trends ───────────────────────────────────────────────────────────────

def _run_time_trends(table_name: str) -> list[dict]:
    with get_conn() as conn:
        schema = conn.execute(f'DESCRIBE "{table_name}"').fetchdf()
        date_cols    = [r["column_name"] for _, r in schema.iterrows() if _is_date(r["column_type"])]
        numeric_cols = [r["column_name"] for _, r in schema.iterrows() if _is_numeric(r["column_type"])][:3]

        if not date_cols:
            return [{"title": "No Date Column", "type": "text",
                     "text": "No DATE or TIMESTAMP column detected."}]

        date_col = date_cols[0]
        sections: list[dict] = [
            {"title": "Date Column Detected", "type": "text",
             "text": f"Using '{date_col}' as the time axis. Grouping by calendar month."},
        ]

        for metric in (numeric_cols or []):
            try:
                df = conn.execute(f"""
                    SELECT
                        DATE_TRUNC('month', CAST("{date_col}" AS DATE))::VARCHAR AS period,
                        COUNT(*)                                 AS record_count,
                        ROUND(SUM("{metric}")::DOUBLE, 2)        AS total,
                        ROUND(AVG("{metric}")::DOUBLE, 2)        AS average
                    FROM "{table_name}"
                    WHERE "{date_col}" IS NOT NULL
                    GROUP BY 1 ORDER BY 1 LIMIT 36
                """).fetchdf()

                if not df.empty:
                    fig = px.line(df, x="period", y="total",
                                  title=f"Monthly Total — {metric}", markers=True,
                                  labels={"period": "Month", "total": f"Total {metric}"})
                    sections.append({"title": f"Monthly Total — {metric}", "type": "chart", "chart_json": fig.to_json()})
                    sections.append({
                        "title": f"Monthly Data — {metric}", "type": "table",
                        "data": df.rename(columns={"period": "Month", "record_count": "Records",
                                                    "total": f"Total {metric}", "average": f"Avg {metric}"}).to_dict(orient="records"),
                    })
            except Exception:
                pass

        if len(sections) == 1:
            sections.append({"title": "No Numeric Columns", "type": "text",
                              "text": "No numeric columns found to plot trends for."})

    return sections


_RUNNERS = {
    "profiling":   _run_profiling,
    "distribution": _run_distribution,
    "outliers":    _run_outliers,
    "correlation": _run_correlation,
    "time_trends": _run_time_trends,
}


# ── Ownership check helper ────────────────────────────────────────────────────

def _check_ownership(table_name: str, user_id: str) -> None:
    with get_conn() as conn:
        in_ownership = conn.execute(
            "SELECT COUNT(*) FROM _dataset_ownership WHERE table_name = ?", [table_name]
        ).fetchone()[0]
        if in_ownership > 0:
            owned = conn.execute(
                "SELECT COUNT(*) FROM _dataset_ownership WHERE table_name = ? AND user_id = ?",
                [table_name, user_id],
            ).fetchone()[0]
            if owned == 0:
                raise HTTPException(status_code=404, detail="Table not found or not accessible.")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/templates")
async def list_templates():
    return [{"id": k, **v} for k, v in TEMPLATES.items()]


@router.post("/run")
async def run_analysis(
    body: AnalysisRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    if body.template not in _RUNNERS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown template '{body.template}'. Valid options: {list(_RUNNERS)}",
        )
    _check_ownership(body.table_name, current_user.id)

    try:
        sections = await asyncio.to_thread(_RUNNERS[body.template], body.table_name)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Analysis failed: {exc}")

    return {
        "template": body.template,
        "template_name": TEMPLATES[body.template]["name"],
        "table_name": body.table_name,
        "sections": sections,
    }


@router.post("/run-all")
async def run_all_analyses(
    body: RunAllRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run all templates against a table. Returns results for each template."""
    _check_ownership(body.table_name, current_user.id)

    results = []
    for template_id, runner in _RUNNERS.items():
        try:
            sections = await asyncio.to_thread(runner, body.table_name)
            results.append({
                "template": template_id,
                "template_name": TEMPLATES[template_id]["name"],
                "sections": sections,
                "error": None,
            })
        except Exception as exc:
            results.append({
                "template": template_id,
                "template_name": TEMPLATES[template_id]["name"],
                "sections": [],
                "error": str(exc),
            })

    return {"table_name": body.table_name, "results": results}
