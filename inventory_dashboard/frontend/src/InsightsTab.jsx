import React, { useState } from "react";

function InsightsTab() {
  const [lookupValue, setLookupValue] = useState("");
  const [poResults, setPoResults] = useState([]);
  const [unitResult, setUnitResult] = useState(null);
  const [expandedRows, setExpandedRows] = useState({});
  const [loading, setLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState("");

  const handleSearch = async () => {
    if (!lookupValue.trim()) return;
    setHasSearched(true);
    setLoading(true);
    setPoResults([]);
    setUnitResult(null);
    setError("");
    try {
      // First try PO search
      const poRes = await fetch(
        `${import.meta.env.VITE_API_HOST}/dashboard/insights/po-details?po_number=${encodeURIComponent(
          lookupValue
        )}`
      );
      const poData = await poRes.json();

      if (poData.length > 0) {
        setPoResults(poData);
        return;
      }

      // If not a PO, try serial
      const snRes = await fetch(
        `${import.meta.env.VITE_API_HOST}/dashboard/insights/unit-details?serial_number=${encodeURIComponent(
          lookupValue
        )}`
      );

      if (!snRes.ok) throw new Error("Not found");
      const snData = await snRes.json();
      setUnitResult(snData);
    } catch (err) {
      setError(`No results found for: ${lookupValue}`);
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
      <h2 className="text-xl font-bold mb-4">Lookup</h2>

      <div className="flex items-center gap-2 mb-4">
        <input
          value={lookupValue}
          onChange={(e) => setLookupValue(e.target.value)}
          placeholder="Enter PO number or serial number..."
          className="border px-3 py-2 rounded w-80"
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
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : unitResult ? (
        <table className="w-full border border-gray-300">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="border px-3 py-2">SKU</th>
              <th className="border px-3 py-2">Product</th>
              <th className="border px-3 py-2">Date Received</th>
              <th className="border px-3 py-2">Sold</th>
              <th className="border px-3 py-2">Damaged</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td className="border px-3 py-2 font-bold">{unitResult.sku}</td>
              <td className="border px-3 py-2">{unitResult.product_name}</td>
              <td className="border px-3 py-2">{unitResult.received_date}</td>
              <td className="border px-3 py-2">{unitResult.sold ? "Yes" : "No"}</td>
              <td className="border px-3 py-2">{unitResult.is_damaged ? "Yes" : "No"}</td>
            </tr>
          </tbody>
        </table>
      ) : poResults.length > 0 ? (
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
            {poResults.map((row, idx) => (
              <React.Fragment key={idx}>
                <tr
                  onClick={() => toggleRow(idx)}
                  className="cursor-pointer hover:bg-gray-50"
                >
                  <td className="border px-3 py-2 font-bold">{row.sku}</td>
                  <td className="border px-3 py-2">{row.product_name}</td>
                  <td className="border px-3 py-2">{row.received_date}</td>
                  <td className="border px-3 py-2">
                    {row.serials?.length ?? 0}
                  </td>
                </tr>
                {expandedRows[idx] && (
                  <tr>
                    <td colSpan="4" className="bg-gray-50 px-4 py-2">
                      <ul className="list-disc list-inside text-sm text-gray-700">
                        {(row.serials ?? []).map((sn, i) => (
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
      ) : null}
    </div>
  );
}

export default InsightsTab;
