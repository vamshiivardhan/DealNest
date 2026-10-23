import React, { useState, useEffect } from "react";

const LOCATIONS = [
  "All locations",
  "ASHOK NAGAR MANORAMA NILAYAM HYDERABAD",
  "SUBHAGRUHA SANVI KANDLAKOYA",
  "GUDIMALKAPUR",
  "WAYANAD"
];

const PLATFORMS = [
  { id: "all", name: "All Platforms" },
  { id: 1, name: "BigBasket" },
  { id: 2, name: "JioMart" }
];

export default function App() {
  const [deals, setDeals] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Filter States
  const [selectedLocation, setSelectedLocation] = useState("All locations");
  const [selectedPlatform, setSelectedPlatform] = useState("all");
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");

  // Debounce search input by 300ms
  useEffect(() => {
    const handler = setTimeout(() => {
      setDebouncedSearch(searchQuery);
    }, 300);
    return () => clearTimeout(handler);
  }, [searchQuery]);

  // Fetch Deals whenever filters change
  useEffect(() => {
    const fetchDeals = async () => {
      setLoading(true);
      setError(null);

      const params = new URLSearchParams();
      if (selectedLocation !== "All locations") {
        params.append("location", selectedLocation);
      }
      if (debouncedSearch.trim()) {
        params.append("search", debouncedSearch.trim());
      }
      if (selectedPlatform !== "all") {
        params.append("platform_id", selectedPlatform);
      }
      params.append("limit", "100");

      try {
        const response = await fetch(`http://127.0.0.1:8000/api/v1/deals?${params.toString()}`);
        if (!response.ok) {
          throw new Error(`Server returned error: ${response.status}`);
        }
        const data = await response.json();
        setDeals(data);
      } catch (err) {
        console.error("Error fetching deals:", err);
        setError("Failed to load deals. Please verify that the backend is running on port 8000.");
      } finally {
        setLoading(false);
      }
    };

    fetchDeals();
  }, [selectedLocation, selectedPlatform, debouncedSearch]);

  const calculateDiscount = (sellingPrice, mrp) => {
    if (!mrp || mrp <= sellingPrice) return null;
    const diff = mrp - sellingPrice;
    const percent = Math.round((diff / mrp) * 100);
    return { percent, diff: Math.round(diff) };
  };

  return (
    <div className="min-h-screen bg-[#0e0f12] text-[#f2ede4] font-sans antialiased selection:bg-[#2c2d38]">
      {/* Top Navigation Bar */}
      <header className="sticky top-0 z-30 border-b border-[#21222a] bg-[#121318]/90 backdrop-blur-md px-6 py-3.5">
        <div className="max-w-7xl mx-auto flex flex-col md:flex-row md:items-center justify-between gap-4">
          
          {/* Logo & Platform Title */}
          <div className="flex items-center gap-3">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f2ede4] text-[#0e0f12] font-black text-sm">
              DN
            </span>
            <div>
              <h1 className="text-base font-bold tracking-tight text-[#f2ede4]">
                DealNest
              </h1>
              <p className="text-[10px] text-[#6e707e] font-medium tracking-wide uppercase">
                Smart Grocery Aggregator
              </p>
            </div>
          </div>

          {/* Search Bar */}
          <div className="relative flex-1 max-w-md">
            <svg
              className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-[#5e6070]"
              fill="none"
              stroke="currentColor"
              viewBox="0 0 24 24"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
            </svg>
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search products or brands..."
              className="w-full bg-[#181920] border border-[#272834] rounded-lg pl-10 pr-4 py-2 text-xs text-[#f2ede4] placeholder-[#5e6070] focus:outline-none focus:border-[#4d5064] transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-[#5e6070] hover:text-[#f2ede4]"
              >
                ✕
              </button>
            )}
          </div>

          {/* Location Dropdown Hub */}
          <div className="flex items-center gap-2">
            <select
              value={selectedLocation}
              onChange={(e) => setSelectedLocation(e.target.value)}
              className="bg-[#181920] border border-[#272834] text-[#f2ede4] text-xs font-semibold uppercase tracking-wider py-2 px-3 rounded-lg focus:outline-none focus:border-[#4d5064] cursor-pointer"
            >
              {LOCATIONS.map((loc) => (
                <option key={loc} value={loc} className="bg-[#121318] text-[#f2ede4]">
                  {loc}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Platform Selection Filter Tabs */}
        <div className="max-w-7xl mx-auto flex items-center gap-2 mt-3 pt-3 border-t border-[#1c1d25]">
          {PLATFORMS.map((platform) => (
            <button
              key={platform.id}
              onClick={() => setSelectedPlatform(platform.id)}
              className={`text-xs px-3 py-1.5 rounded-md font-medium tracking-wide transition-colors ${
                selectedPlatform === platform.id
                  ? "bg-[#252632] text-[#ffffff] border border-[#393b4c]"
                  : "bg-transparent text-[#767888] hover:text-[#c4c1ba]"
              }`}
            >
              {platform.name}
            </button>
          ))}
          <span className="ml-auto text-[11px] text-[#5e6070] font-medium">
            Showing {deals.length} deals
          </span>
        </div>
      </header>

      {/* Main Content Area */}
      <main className="max-w-7xl mx-auto p-6">
        {error && (
          <div className="mb-6 p-4 rounded-lg bg-red-950/40 border border-red-800 text-red-200 text-xs">
            {error}
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4 animate-pulse">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="h-80 bg-[#16171e] rounded-xl border border-[#21222b]"></div>
            ))}
          </div>
        ) : deals.length === 0 ? (
          <div className="text-center py-24">
            <p className="text-sm text-[#7e8092]">No matching deals found for the selected criteria.</p>
            <button
              onClick={() => {
                setSelectedLocation("All locations");
                setSelectedPlatform("all");
                setSearchQuery("");
              }}
              className="mt-3 text-xs text-[#a2a5b8] underline underline-offset-4 hover:text-[#ffffff]"
            >
              Reset all filters
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
            {deals.map((deal) => {
              const discount = calculateDiscount(deal.current_selling_price, deal.current_mrp);

              return (
                <div
                  key={deal.id}
                  className="group bg-[#15161d] border border-[#22232c] hover:border-[#323442] rounded-xl p-4 flex flex-col justify-between transition-all duration-150"
                >
                  <div>
                    {/* Top Badges (Platform & Discount) */}
                    <div className="flex items-center justify-between mb-2.5">
                      <span className="text-[10px] font-semibold tracking-wider text-[#686a79] uppercase">
                        {deal.platform_id === 1 ? "BigBasket" : "JioMart"}
                      </span>
                      {discount && (
                        <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-[#20222a] border border-[#2d2f3b] text-[#d6d2cb]">
                          -{discount.percent}%
                        </span>
                      )}
                    </div>

                    {/* Product Image */}
                    <div className="w-full h-40 bg-[#1b1c24] rounded-lg overflow-hidden flex items-center justify-center mb-3.5 p-2">
                      {deal.image_url ? (
                        <img
                          src={deal.image_url}
                          alt={deal.raw_title}
                          className="max-h-full max-w-full object-contain group-hover:scale-105 transition-transform duration-200"
                          loading="lazy"
                        />
                      ) : (
                        <div className="text-[11px] text-[#484a56] font-medium">No Image</div>
                      )}
                    </div>

                    {/* Product Title */}
                    <h3 className="text-xs font-medium text-[#e3ded6] line-clamp-2 leading-relaxed">
                      {deal.raw_title}
                    </h3>
                  </div>

                  {/* Pricing, Hub and Action */}
                  <div className="mt-4 pt-3 border-t border-[#1e1f28]">
                    <div className="flex items-baseline gap-2 mb-2">
                      <span className="text-base font-bold text-[#ffffff]">
                        ₹{deal.current_selling_price}
                      </span>
                      {deal.current_mrp && deal.current_mrp > deal.current_selling_price && (
                        <span className="text-xs text-[#636574] line-through">
                          ₹{deal.current_mrp}
                        </span>
                      )}
                      {discount && (
                        <span className="text-[10px] text-[#868897] ml-auto">
                          Save ₹{discount.diff}
                        </span>
                      )}
                    </div>

                    {/* Location Pin */}
                    <div className="text-[10px] text-[#6e7080] uppercase tracking-wider mb-3 flex items-center gap-1.5 font-medium">
                      <svg className="w-3 h-3 text-[#505260] shrink-0" fill="currentColor" viewBox="0 0 20 20">
                        <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                      </svg>
                      <span className="truncate">{deal.location || "GUDIMALKAPUR"}</span>
                    </div>

                    {/* External Link Button */}
                    <a
                      href={deal.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block w-full py-2 bg-[#f2ede4] hover:bg-[#ded9cf] text-[#121318] text-center font-bold text-[11px] uppercase tracking-wider rounded-lg transition-colors"
                    >
                      Grab Deal ↗
                    </a>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
