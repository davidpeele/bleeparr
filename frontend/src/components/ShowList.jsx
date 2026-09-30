import { useState, useEffect } from 'react';

function ShowList() {
  const [shows, setShows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // Fetch shows and filtered flags from backend
  useEffect(() => {
    Promise.all([
      fetch("/api/shows").then((res) => res.json()),
      fetch("/api/filtered/show").then((res) => res.json())
    ])
      .then(([showData, filteredData]) => {
        const filteredMap = {};
        filteredData.forEach((item) => {
          filteredMap[item.series_id] = item.filtered;
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

  const toggleFiltered = async (seriesId, current) => {
    const newValue = !current;
    try {
      await fetch(`/api/filtered/${seriesId}?filtered=${newValue}`, {
        method: "PUT"
      });
      setShows((prev) =>
        prev.map((show) =>
          show.id === seriesId ? { ...show, filtered: newValue } : show
        )
      );
    } catch (err) {
      console.error("Failed to update filtered flag:", err);
    }
  };

  const handleToggle = (id, newValue) => {
    fetch(`/api/filtered/show/${id}?filtered=${newValue}`, { method: "PUT" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        setShows((prev) =>
          prev.map((show) =>
            show.id === id ? { ...show, filtered: newValue } : show
          )
        );
      })
      .catch((err) => console.error("Failed to update filtered flag:", err));
  };

  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-2">TV Shows from Sonarr</h2>
      {loading ? (
        <p>Loading shows...</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <table className="min-w-full border border-gray-200">
          <thead>
            <tr className="bg-gray-100">
              <th className="p-2 text-left">Title</th>
              <th className="p-2 text-left">Monitored</th>
              <th className="p-2 text-left">Filtered</th>
            </tr>
          </thead>
          <tbody>
            {shows.map((show) => (
              <tr key={show.id} className="border-t">
                <td className="p-2">{show.title}</td>
                <td className="p-2">{show.monitored ? "Yes" : "No"}</td>
                <td className="p-2">
                  <input
                    type="checkbox"
                    checked={show.filtered}
		    onChange={() => handleToggle(show.id, !show.filtered)}
                  />
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
