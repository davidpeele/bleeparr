import { useState, useEffect } from 'react';

function ShowList() {
  const [shows, setShows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('title');
  const [sortDirection, setSortDirection] = useState('asc');
  const [processing, setProcessing] = useState({});

  // Fetch shows and filtered flags from backend
  useEffect(() => {
    Promise.all([
      fetch("/api/shows").then((res) => res.json()),
      fetch("/api/filtered/show").then((res) => res.json())
    ])
      .then(([showData, filteredData]) => {
        const filteredMap = {};
        filteredData.forEach((item) => {
          filteredMap[item.id] = item.filtered;
        });

        const merged = showData.map((show) => ({
          ...show,
          filtered: filteredMap[show.id] || false,
        }));

        setShows(merged);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading shows or filtered flags:", err);
        setError("Failed to load shows.");
        setLoading(false);
      });
  }, []);

  // Filter shows based on search term
  const filteredShows = shows.filter(show => 
    show.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Sort shows based on sort field and direction
  const sortedShows = [...filteredShows].sort((a, b) => {
    if (sortField === 'title') {
      return sortDirection === 'asc' 
        ? a.title.localeCompare(b.title)
        : b.title.localeCompare(a.title);
    } else if (sortField === 'status') {
      return sortDirection === 'asc'
        ? (a.status || '').localeCompare(b.status || '')
        : (b.status || '').localeCompare(a.status || '');
    }
    return 0;
  });

  const handleToggle = (id, newValue) => {
    fetch(`/api/filtered/show/${id}?filtered=${newValue}`, { method: "PUT" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        return res.json();
      })
      .then((data) => {
        setShows((prev) =>
          prev.map((show) =>
            show.id === id ? { ...show, filtered: data.filtered } : show
          )
        );
      })
      .catch((err) => console.error("Failed to update filtered flag:", err));
  };

  const handleProcessShow = (id) => {
    setProcessing(prev => ({ ...prev, [id]: true }));
    
    fetch(`/api/process/series/${id}`, { 
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to process show");
        return res.json();
      })
      .then((data) => {
        alert(`Processing ${data.queued_count} episodes from this show.`);
      })
      .catch((err) => {
        console.error("Failed to process show:", err);
        alert("Failed to process show. See console for details.");
      })
      .finally(() => {
        setProcessing(prev => ({ ...prev, [id]: false }));
      });
  };

  const handleSort = (field) => {
    if (field === sortField) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-2">TV Shows from Sonarr</h2>
      
      <div className="mb-4 flex justify-between items-center">
        <input
          type="text"
          placeholder="Search shows..."
          className="px-4 py-2 border rounded-md w-64"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <div className="text-sm text-gray-600">
          {filteredShows.length} of {shows.length} shows
        </div>
      </div>
      
      {loading ? (
        <p>Loading shows...</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <table className="min-w-full border border-gray-200">
          <thead>
            <tr className="bg-gray-100">
              <th 
                className="p-2 text-left cursor-pointer"
                onClick={() => handleSort('title')}
              >
                Title
                {sortField === 'title' && (
                  <span className="ml-1">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="p-2 text-left">Monitored</th>
              <th className="p-2 text-left">Status</th>
              <th 
                className="p-2 text-left cursor-pointer"
                onClick={() => handleSort('status')}
              >
                Filter
                {sortField === 'status' && (
                  <span className="ml-1">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="p-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedShows.map((show) => (
              <tr key={show.id} className="border-t hover:bg-gray-50">
                <td className="p-2">
                  <div className="font-medium">{show.title}</div>
                  {show.year && <div className="text-sm text-gray-600">{show.year}</div>}
                </td>
                <td className="p-2">{show.monitored ? "Yes" : "No"}</td>
                <td className="p-2">{show.status || "-"}</td>
                <td className="p-2">
                  <label className="inline-flex items-center">
                    <input
                      type="checkbox"
                      className="form-checkbox h-5 w-5 text-blue-600"
                      checked={show.filtered}
                      onChange={() => handleToggle(show.id, !show.filtered)}
                    />
                    <span className="ml-2">Filter Profanity</span>
                  </label>
                </td>
                <td className="p-2">
                  <button
                    className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50"
                    onClick={() => handleProcessShow(show.id)}
                    disabled={!show.filtered || processing[show.id]}
                  >
                    {processing[show.id] ? "Processing..." : "Process All Episodes"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}

export default ShowList;
