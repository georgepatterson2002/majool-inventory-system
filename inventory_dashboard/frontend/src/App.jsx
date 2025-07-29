// App.jsx
import React, { useEffect, useState } from "react";
import InsightsTab from "./InsightsTab";
import { ArrowDownTrayIcon } from "@heroicons/react/24/solid";


const API_HOST = import.meta.env.VITE_API_HOST;

function App() {
  const [products, setProducts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedSkus, setExpandedSkus] = useState(new Set());
  const [log, setLog] = useState({});
  const [manualCheckItems, setManualCheckItems] = useState([]);
  const [skuBreakdowns, setSkuBreakdowns] = useState({});
  const [activeTab, setActiveTab] = useState(() => {
  return localStorage.getItem("activeTab") || "warehouse";
});
  const [expandedOrders, setExpandedOrders] = useState(new Set());

  useEffect(() => {
  fetchData();
  fetchInventoryLog();
  fetchManualCheckItems();

  const interval = setInterval(() => {
    if (document.visibilityState === "visible") {
      console.log("🔄 Auto-refreshing inventory log at", new Date().toLocaleTimeString());
      fetchInventoryLog();
    }
  }, 60000); // every minute

  return () => clearInterval(interval); // cleanup
}, []);

  const groupByMasterSku = (rows) => {
    const grouped = {};

    for (const row of rows) {
      const masterId = row.master_sku_id.trim();
      if (!grouped[masterId]) {
        grouped[masterId] = {
          master_sku_id: masterId,
          description: row.description,
          quantity: 0
        };
      }

      grouped[masterId].quantity += Number(row.quantity || 0);
    }

    return Object.values(grouped);
  };

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${import.meta.env.VITE_API_HOST}/dashboard/grouped-products`);
      const raw = await res.json();
      const grouped = groupByMasterSku(raw);
      setProducts(grouped);
    } catch (err) {
      console.error("❌ Error fetching grouped products", err);
    } finally {
      setLoading(false);
    }
  };

  const fetchInventoryLog = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_HOST}/dashboard/inventory-log`);
      const data = await res.json();

      const sevenDaysAgo = new Date();
      sevenDaysAgo.setDate(sevenDaysAgo.getDate() - 7);

      const grouped = {};
      for (const entry of data) {
        const eventTime = new Date(entry.event_time);
        if (eventTime >= sevenDaysAgo) {
          const id = entry.order_id ?? "unknown";
          if (!grouped[id]) grouped[id] = [];
          grouped[id].push(entry);
        }
      }

      setLog(grouped);
    } catch (err) {
      console.error("❌ Failed to load inventory log", err);
    }
  };

  const toggleSkuBreakdown = async (masterSkuId) => {
    const newSet = new Set(expandedSkus);
    if (expandedSkus.has(masterSkuId)) {
      newSet.delete(masterSkuId);
    } else {
      newSet.add(masterSkuId);
      if (!skuBreakdowns[masterSkuId]) {
        try {
          const res = await fetch(`${API_HOST}/dashboard/sku-breakdown?master_sku_id=${masterSkuId}`);
          const data = await res.json();
          setSkuBreakdowns(prev => ({ ...prev, [masterSkuId]: data }));
        } catch (err) {
          console.error("❌ Error fetching breakdown", err);
        }
      }
    }
    setExpandedSkus(newSet);
  };


  const fetchManualCheckItems = async () => {
    try {
      const res = await fetch(`${import.meta.env.VITE_API_HOST}/dashboard/manual-check`);
      const data = await res.json();
      setManualCheckItems(data);
    } catch (err) {
      console.error("❌ Failed to fetch manual check items", err);
    }
  };

  const downloadCSV = async () => {
    const now = new Date();
    const iso = now.toISOString();
    const dateStr = iso.split("T")[0]; // YYYY-MM-DD

    const res = await fetch(`${import.meta.env.VITE_API_HOST}/dashboard/insights/monthly-report?cutoff=${iso}`);
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `monthly_report_${dateStr}.csv`;  // <-- dynamic filename
    link.click();
  };

  const handleTabChange = (tab) => {
  setActiveTab(tab);
  localStorage.setItem("activeTab", tab);
};

  if (loading) return <div className="p-6 text-center">Loading inventory...</div>;

  return (
    <div className="p-6">



      <div className="flex justify-between items-center mb-4">
  <h1 className="text-2xl font-bold">📦 Inventory</h1>

</div>




      <div className="flex justify-between items-center mb-6">
        {/* Tab Buttons (left side) */}
        <div className="flex gap-4">
          <button
            onClick={() => handleTabChange("warehouse")}
            className={`px-4 py-2 rounded ${activeTab === "warehouse" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"}`}
          >📦 Warehouse</button>

          <button
            onClick={() => handleTabChange("log")}
            className={`px-4 py-2 rounded ${activeTab === "log" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"}`}
          >📋 Shipped Log</button>

          <button
            onClick={() => handleTabChange("manual")}
            className={`px-4 py-2 rounded flex items-center gap-1 ${
              activeTab === "manual" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"
            }`}
          >
            🛠️ Manual Review
            {manualCheckItems.length > 0 && (
              <span
                className={`ml-1 text-xs font-semibold px-2 py-0.5 rounded-full ${
                  activeTab === "manual" ? "bg-white text-blue-600" : "bg-blue-600 text-white"
                }`}
              >
                {manualCheckItems.length > 5 ? "5+" : manualCheckItems.length}
              </span>
            )}
          </button>

          <button
            onClick={() => handleTabChange("insights")}
            className={`px-4 py-2 rounded ${activeTab === "insights" ? "bg-blue-600 text-white" : "bg-gray-200 text-gray-700"}`}
          >
            📊 Insights
          </button>
        </div>

        {/* Right side: CSV download button (warehouse only) */}
        {activeTab === "warehouse" && (
          <button
            onClick={downloadCSV}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 flex items-center gap-2"
          >
            <ArrowDownTrayIcon className="h-5 w-5 text-white" />
            Download CSV
          </button>
        )}
      </div>

      {activeTab === "warehouse" && (
        <table className="w-full border border-gray-300">
          <thead className="bg-gray-100 text-left">
            <tr>
              <th className="border px-3 py-2">Master SKU</th>
              <th className="border px-3 py-2">Product</th>
              <th className="border px-3 py-2">Qty</th>
            </tr>
          </thead>
          <tbody>
            {products
              .slice()
              .sort((a, b) =>
                (a.master_sku_id.startsWith("MSKU-") ? a.master_sku_id.slice(5) : a.master_sku_id).localeCompare(
                  b.master_sku_id.startsWith("MSKU-") ? b.master_sku_id.slice(5) : b.master_sku_id,
                  undefined,
                  { numeric: true, sensitivity: "base" }
                )
              )
              .flatMap((row) => {
                const isOpen = expandedSkus.has(row.master_sku_id);
                const rows = [];

                // main row
                rows.push(
                  <tr
                    key={row.master_sku_id}
                    className="hover:bg-gray-100 cursor-pointer font-semibold"
                    onClick={() => toggleSkuBreakdown(row.master_sku_id)}
                  >
                    <td className="border px-3 py-2 font-mono text-gray-800">
                      {row.master_sku_id.replace(/^MSKU-/, "")}
                    </td>
                    <td className="border px-3 py-2">{row.description}</td>
                    <td className="border px-3 py-2">{row.quantity}</td>
                  </tr>
                );

                // expanded rows
                if (isOpen && Array.isArray(skuBreakdowns[row.master_sku_id])) {
                  skuBreakdowns[row.master_sku_id].forEach((item, idx) => {
                    rows.push(
                      <tr key={`${row.master_sku_id}-${item.sku}-${idx}`} className="text-sm bg-white">
                        <td className="border px-3 py-1 pl-6">
                          <span className="text-gray-500">SKU:</span> {item.sku}
                        </td>
                        <td className="border px-3 py-1">
                          <span className="text-gray-500">Qty:</span> {item.qty}
                        </td>
                        <td className="border px-3 py-1">
                          {item.sku !== "Damaged" && (
                            <div className="flex items-center relative">
                              <span className="mr-1">$</span>
                              <input
                                type="number"
                                step="0.01"
                                className="border rounded px-1 w-20 no-spin"
                                value={item.price ?? ""}
                                onFocus={() => {
                                  setSkuBreakdowns(prev => ({
                                    ...prev,
                                    [row.master_sku_id]: prev[row.master_sku_id].map(x =>
                                      x.product_id === item.product_id ? { ...x, _focused: true } : x
                                    )
                                  }));
                                }}
                                onBlur={() => {
                                  setSkuBreakdowns(prev => ({
                                    ...prev,
                                    [row.master_sku_id]: prev[row.master_sku_id].map(x =>
                                      x.product_id === item.product_id ? { ...x, _focused: false } : x
                                    )
                                  }));
                                }}
                                onChange={(e) => {
                                  const val = e.target.value;
                                  setSkuBreakdowns(prev => ({
                                    ...prev,
                                    [row.master_sku_id]: prev[row.master_sku_id].map(x =>
                                      x.product_id === item.product_id ? { ...x, price: val } : x
                                    )
                                  }));
                                }}
                              />
                              {item._focused && (
                                <button
                                  className="ml-2 px-2 bg-blue-500 text-white rounded hover:bg-blue-600"
                                  onMouseDown={async (e) => {
                                    e.preventDefault();
                                    const val = item.price === "" ? null : parseFloat(item.price);

                                    if (val !== null && !isNaN(val)) {
                                      await fetch(`${API_HOST}/dashboard/product-price`, {
                                        method: "POST",
                                        headers: { "Content-Type": "application/json" },
                                        body: JSON.stringify({ product_id: item.product_id, price: val })
                                      });

                                      const res = await fetch(`${API_HOST}/dashboard/sku-breakdown?master_sku_id=${row.master_sku_id}`);
                                      const data = await res.json();
                                      setSkuBreakdowns(prev => ({ ...prev, [row.master_sku_id]: data }));
                                    }
                                  }}
                                >
                                  Save
                                </button>
                              )}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  });
                }

                return rows;
              })}
          </tbody>

        </table>
      )}




 {/* Inventory Log Table */}
      {activeTab === "log" && (
  <div>
    {log && Object.keys(log).length === 0 ? (
      <p className="text-gray-600">No recent inventory actions.</p>
    ) : (
      <table className="w-full border border-gray-300">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="border px-3 py-2">Order ID</th>
            <th className="border px-3 py-2"># Items</th>
            <th className="border px-3 py-2">Shipped At</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(log).map(([orderId, entries]) => {
            const isOpen = expandedOrders.has(orderId);
            const toggle = () => {
              const newSet = new Set(expandedOrders);
              isOpen ? newSet.delete(orderId) : newSet.add(orderId);
              setExpandedOrders(newSet);
            };

            return (
              <React.Fragment key={orderId}>
                <tr
                  onClick={toggle}
                  className="hover:bg-gray-100 cursor-pointer font-semibold"
                >
                  <td className="border px-3 py-2">{orderId}</td>
                  <td className="border px-3 py-2">{entries.length}</td>
                  <td className="border px-3 py-2 text-sm text-gray-600">
                    {new Date(
                      Math.max(...entries.map((e) => new Date(e.event_time).getTime()))
                    ).toLocaleString('en-US', { timeZone: 'America/Los_Angeles' })}
                  </td>
                </tr>
                {isOpen &&
                  entries.map((entry, idx) => (
                    <tr key={idx} className="text-sm bg-white">
                      <td className="border px-3 py-1 pl-6">
                        <span className="text-gray-500">SKU:</span> {entry.sku}
                      </td>
                      <td className="border px-3 py-1">
                        <span className="text-gray-500">Serial:</span>{" "}
                        {entry.serial_number}
                      </td>
                    </tr>
                  ))}
              </React.Fragment>
            );
          })}
        </tbody>
      </table>
    )}
  </div>
)}

 {/* Manual Table */}
{activeTab === "manual" && (
  <div>
    {!Array.isArray(manualCheckItems) ? (
      <p className="text-red-600">Error loading items.</p>
    ) : manualCheckItems.length === 0 ? (
      <p className="text-gray-600">All items are accounted for.</p>
    ) : (
      <table className="w-full border border-gray-300">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="border px-3 py-2">Order ID</th>
            <th className="border px-3 py-2">SKU</th>
            <th className="border px-3 py-2">Reported Ship Time</th>
          </tr>
        </thead>
        <tbody>
          {manualCheckItems.map((item) => (
            <tr key={item.id} className="hover:bg-gray-50">
              <td className="border px-3 py-2 font-semibold">{item.order_id}</td>
              <td className="border px-3 py-2">{item.sku}</td>
              <td className="border px-3 py-2 text-sm text-gray-600">
                {new Date(item.created_at).toLocaleString()}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </div>
)}
  {/* Insights Tab */}
{activeTab === "insights" && <InsightsTab />}
    </div>
  );
}

export default App;
