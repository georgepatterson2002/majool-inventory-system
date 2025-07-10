import React, { useState } from "react";

function InsightsTab() {
  const [poNumber, setPoNumber] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  const handleSearch = async () => {
    if (!poNumber.trim()) return;

    setHasSearched(true); // ← Track that the user submitted a search
    setLoading(true);

    setLoading(true);
    try {
      const res = await fetch(`/api/insights/po-summary?po_number=${encodeURIComponent(poNumber)}`);
      const data = await res.json();
      setResults(data);
    } catch (err) {
      console.error("Failed to load PO summary", err);
      setResults([]);
    } finally {
      setLoading(false);
    }
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
        results.length > 0 && (
          <table className="w-full border border-gray-300">
            <thead className="bg-gray-100 text-left">
              <tr>
                <th className="border px-3 py-2">SKU</th>
                <th className="border px-3 py-2">Product</th>
                <th className="border px-3 py-2">Date Received</th>
                <th className="border px-3 py-2">Quantity</th>
              </tr>
            </thead>
            <tbody>
              {results
                .sort((a, b) => new Date(b.received_date) - new Date(a.received_date))
                .map((row, idx) => (
                  <tr key={idx}>
                    <td className="border px-3 py-2">{row.sku}</td>
                    <td className="border px-3 py-2">{row.product_name}</td>
                    <td className="border px-3 py-2">{row.received_date}</td>
                    <td className="border px-3 py-2">{row.quantity}</td>
                  </tr>
              ))}
            </tbody>
          </table>
        )
      )}
    </div>
  );
}

export default InsightsTab;
