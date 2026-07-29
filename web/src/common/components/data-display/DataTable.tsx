import type { ReactNode } from "react";

import "./DataTable.css";

export interface DataTableColumn<TRow> {
  header: string;
  key: string;
  render: (row: TRow) => ReactNode;
}

interface DataTableProps<TRow> {
  caption: string;
  columns: readonly DataTableColumn<TRow>[];
  emptyMessage?: string;
  getRowKey: (row: TRow) => string;
  rows: readonly TRow[];
}

export default function DataTable<TRow>({
  caption,
  columns,
  emptyMessage = "표시할 데이터가 없습니다.",
  getRowKey,
  rows,
}: DataTableProps<TRow>) {
  return (
    <div className="common-data-table-wrap">
      <table className="common-data-table">
        <caption>{caption}</caption>
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} scope="col">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className="common-data-table__empty" colSpan={columns.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={getRowKey(row)}>
                {columns.map((column) => (
                  <td key={column.key}>{column.render(row)}</td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
