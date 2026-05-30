"use client"

import dynamic from "next/dynamic"

// Plotly is browser-only — must be dynamically imported with ssr: false
const Plot = dynamic(() => import("react-plotly.js"), { ssr: false })

interface PlotlyTableTrace {
  type: "table"
  header: { values: string[] }
  cells: { values: unknown[][] }
}

interface Props {
  chartJson: string
}

function isTableFigure(data: unknown[]): data is [PlotlyTableTrace] {
  return data.length > 0 && (data[0] as { type?: string }).type === "table"
}

function stripHtml(s: string): string {
  return s.replace(/<[^>]+>/g, "")
}

export function ChartMessage({ chartJson }: Props) {
  let figure: { data: unknown[]; layout: Record<string, unknown> }
  try {
    figure = JSON.parse(chartJson)
  } catch {
    return null
  }

  // Tabular results → native HTML table (unambiguously a table, not a chart widget)
  if (isTableFigure(figure.data)) {
    const trace = figure.data[0]
    const headers = trace.header.values.map(stripHtml)
    const numRows = Math.max(...trace.cells.values.map((col) => col.length), 0)
    // cells.values is column-oriented — transpose to row-oriented for rendering
    const rows = Array.from({ length: numRows }, (_, i) =>
      trace.cells.values.map((col) => String(col[i] ?? ""))
    )

    return (
      <div className="w-full overflow-x-auto rounded-xl border bg-background">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="bg-primary/10">
              {headers.map((h, i) => (
                <th key={i} className="px-3 py-2 text-left font-semibold text-foreground border-b whitespace-nowrap">
                  {h}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.length === 0 ? (
              <tr>
                <td colSpan={headers.length} className="px-3 py-4 text-center text-muted-foreground">
                  No results
                </td>
              </tr>
            ) : (
              rows.map((row, ri) => (
                <tr key={ri} className={ri % 2 === 1 ? "bg-muted/30" : ""}>
                  {row.map((cell, ci) => (
                    <td key={ci} className="px-3 py-2 text-foreground border-b border-border/40">
                      {cell}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    )
  }

  // Charts (bar, line, scatter) → interactive Plotly widget
  return (
    <div className="w-full overflow-x-auto rounded-xl border bg-background p-2">
      <Plot
        data={figure.data as Plotly.Data[]}
        layout={{
          ...figure.layout,
          autosize: true,
          margin: { l: 40, r: 20, t: 40, b: 60 },
          paper_bgcolor: "transparent",
          plot_bgcolor: "transparent",
          font: { size: 12 },
        }}
        config={{ displayModeBar: "hover", responsive: true, displaylogo: false }}
        style={{ width: "100%", minHeight: "300px" }}
        useResizeHandler
      />
    </div>
  )
}
