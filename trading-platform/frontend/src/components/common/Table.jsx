import React, { useState, useMemo } from 'react';
import LoadingSpinner from './LoadingSpinner';

export const Table = ({
  columns = [],
  data = [],
  loading = false,
  emptyMessage = 'No records found',
  rowKey = 'id',
  onRowClick = null,
  className = ''
}) => {
  const [sortField, setSortField] = useState(null);
  const [sortAsc, setSortAsc] = useState(true);

  const handleSort = (field) => {
    if (!field) return;
    if (sortField === field) {
      setSortAsc(!sortAsc);
    } else {
      setSortField(field);
      setSortAsc(true);
    }
  };

  const sortedData = useMemo(() => {
    if (!sortField || !Array.isArray(data)) return data;
    return [...data].sort((a, b) => {
      let valA = a[sortField];
      let valB = b[sortField];

      if (valA === undefined || valA === null) valA = '';
      if (valB === undefined || valB === null) valB = '';

      if (typeof valA === 'number' && typeof valB === 'number') {
        return sortAsc ? valA - valB : valB - valA;
      }
      return sortAsc
        ? String(valA).localeCompare(String(valB))
        : String(valB).localeCompare(String(valA));
    });
  }, [data, sortField, sortAsc]);

  if (loading) {
    return (
      <div className="py-12 flex items-center justify-center">
        <LoadingSpinner text="Fetching market records..." />
      </div>
    );
  }

  return (
    <div className={`w-full overflow-x-auto rounded-lg border border-slate-800/80 bg-[#0d121e]/60 ${className}`}>
      <table className="w-full text-left text-xs border-collapse">
        <thead className="bg-[#111827]/80 text-slate-400 uppercase text-[10px] tracking-wider border-b border-slate-800">
          <tr>
            {columns.map((col, idx) => (
              <th
                key={col.key || idx}
                onClick={() => col.sortable && handleSort(col.key)}
                className={`px-4 py-3 font-semibold select-none ${
                  col.sortable ? 'cursor-pointer hover:text-slate-200 transition-colors' : ''
                } ${col.align === 'right' ? 'text-right' : col.align === 'center' ? 'text-center' : 'text-left'}`}
              >
                <div className={`inline-flex items-center gap-1.5 ${col.align === 'right' ? 'justify-end' : ''}`}>
                  <span>{col.label}</span>
                  {col.sortable && sortField === col.key && (
                    <span className="text-cyan-400">{sortAsc ? '▲' : '▼'}</span>
                  )}
                </div>
              </th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-800/40 font-mono">
          {sortedData.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="text-center py-10 text-slate-500 font-sans italic">
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, rIdx) => {
              const key = row[rowKey] || rIdx;
              return (
                <tr
                  key={key}
                  onClick={() => onRowClick && onRowClick(row)}
                  className={`hover:bg-slate-800/40 transition-colors duration-150 ${
                    onRowClick ? 'cursor-pointer' : ''
                  }`}
                >
                  {columns.map((col, cIdx) => (
                    <td
                      key={col.key || cIdx}
                      className={`px-4 py-3 whitespace-nowrap text-slate-300 ${
                        col.align === 'right'
                          ? 'text-right'
                          : col.align === 'center'
                          ? 'text-center'
                          : 'text-left'
                      } ${col.className || ''}`}
                    >
                      {col.render ? col.render(row[col.key], row, rIdx) : row[col.key]}
                    </td>
                  ))}
                </tr>
              );
            })
          )}
        </tbody>
      </table>
    </div>
  );
};

export default Table;
