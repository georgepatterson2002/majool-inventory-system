import React, { useState } from "react";

function InsightsTab() {
  const [poNumber, setPoNumber] = useState("");
  const [results, setResults] = useState([]);
  const [expandedRows, setExpandedRows] = useState({});
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    if (!poNumber.trim()) return;
    setHasSearched(true);
    setLoading(true);
    try {
      const res = await fetch(
        `${import.meta.env.VITE_API_HOST}/dashboard/insights/po-details?po_number=${encodeURIComponent(poNumber)}`
      );
      const data = await res.json();
      setResults(data);
      setExpandedRows({}); // reset expansion
    } catch (err) {
      console.error("Failed to load PO details", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
  };

  const toggleRow = (idx) => {
    setExpandedRows((prev) => ({
      ...prev,
      [idx]: !prev[idx]
    }));
  };

  return (
    <div className="p-4">
      <h2 className="text-xl font-bold mb-4">PO Lookup</h2>

      <div className="flex items-center gap-2 mb-4">
        <input
          value={poNumber}
          onChange={(e) => setPoNumber(e.target.value)}
          placeholder="Enter PO number..."
          className="border px-3 py-2 rounded w-64"
        />
        <button
          onClick={handleSearch}
          className="bg-blue-600 text-white px-4 py-2 rounded"
        >
          Search
        </button>
      </div>

      {loading ? (
        <p className="text-gray-600">Loading...</p>
      ) : results.length === 0 && hasSearched ? (
        <p className="text-red-500">No results found for PO: {poNumber}</p>
      ) : (
        <table className="w-full border border-gray-300">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="border px-3 py-2">SKU</th>
              <th className="border px-3 py-2">Product</th>
              <th className="border px-3 py-2">Date Received</th>
              <th className="border px-3 py-2">Serials</th>
            </tr>
          </thead>
          <tbody>
            {results.map((row, idx) => (
              <React.Fragment key={idx}>
                <tr
                  onClick={() => toggleRow(idx)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="border px-3 py-2 font-bold">{row.sku}</td>
                  <td className="border px-3 py-2">{row.product_name}</td>
                  <td className="border px-3 py-2">{row.received_date}</td>
                  <td className="border px-3 py-2">{row.serial_count}</td>
                </tr>
                {expandedRows[idx] && (
                  <tr>
                    <td colSpan="4" className="bg-gray-50 px-4 py-2">
                      <ul className="list-disc list-inside text-sm text-gray-700">
                        {row.serials.map((sn, i) => (
                          <li key={i}>{sn}</li>
                        ))}
                      </ul>
                    </td>
                  </tr>
                )}
              </React.Fragment>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default InsightsTab;
