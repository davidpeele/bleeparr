import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';

function MovieList() {
  const [movies, setMovies] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [sortField, setSortField] = useState('title');
  const [sortDirection, setSortDirection] = useState('asc');
  const [processing, setProcessing] = useState({});
  const navigate = useNavigate();

  // Fetch movies and filtered flags from backend
  useEffect(() => {
    Promise.all([
      fetch("/api/movies").then((res) => res.json()),
      fetch("/api/filtered/movie").then((res) => res.json())
    ])
      .then(([movieData, filteredData]) => {
        const filteredMap = {};
        filteredData.forEach((item) => {
          filteredMap[item.id] = item.filtered;
        });

        const merged = movieData.map((movie) => ({
          ...movie,
          filtered: filteredMap[movie.id] || false,
        }));

        setMovies(merged);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error loading movies or filtered flags:", err);
        setError("Failed to load movies.");
        setLoading(false);
      });
  }, []);

  // Filter movies based on search term
  const filteredMovies = movies.filter(movie => 
    movie.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // Sort movies based on sort field and direction
  const sortedMovies = [...filteredMovies].sort((a, b) => {
    if (sortField === 'title') {
      return sortDirection === 'asc' 
        ? a.title.localeCompare(b.title)
        : b.title.localeCompare(a.title);
    } else if (sortField === 'year') {
      return sortDirection === 'asc'
        ? (a.year || 0) - (b.year || 0)
        : (b.year || 0) - (a.year || 0);
    }
    return 0;
  });

  const handleToggle = (id, newValue) => {
    fetch(`/api/filtered/movie/${id}?filtered=${newValue}`, { method: "PUT" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to update");
        return res.json();
      })
      .then((data) => {
        setMovies((prev) =>
          prev.map((movie) =>
            movie.id === id ? { ...movie, filtered: data.filtered } : movie
          )
        );
      })
      .catch((err) => console.error("Failed to update filtered flag:", err));
  };

  const handleProcessMovie = (id) => {
    setProcessing(prev => ({ ...prev, [id]: true }));
    
    fetch(`/api/process/movie/${id}`, { 
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      }
    })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to process movie");
        return res.json();
      })
      .then((data) => {
        alert(`Movie queued for processing: ${data.message}`);
      })
      .catch((err) => {
        console.error("Failed to process movie:", err);
        alert("Failed to process movie. See console for details.");
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

  const handleMovieClick = (movieId) => {
    navigate(`/movies/${movieId}`);
  };

  // ... modify the movie list rendering to make rows clickable ...
  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-2">Movies from Radarr</h2>
      
      <div className="mb-4 flex justify-between items-center">
        <input
          type="text"
          placeholder="Search movies..."
          className="px-4 py-2 border rounded-md w-64"
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
        />
        <div className="text-sm text-gray-600">
          {filteredMovies.length} of {movies.length} movies
        </div>
      </div>
      
      {loading ? (
        <p>Loading movies...</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : movies.length === 0 ? (
        <div className="bg-yellow-50 p-4 border border-yellow-200 rounded-md">
          <p className="text-yellow-700">No movies found. Make sure your Radarr integration is configured correctly in the Settings panel.</p>
        </div>
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
              <th 
                className="p-2 text-left cursor-pointer"
                onClick={() => handleSort('year')}
              >
                Year
                {sortField === 'year' && (
                  <span className="ml-1">
                    {sortDirection === 'asc' ? '↑' : '↓'}
                  </span>
                )}
              </th>
              <th className="p-2 text-left">Status</th>
              <th className="p-2 text-left">Filter</th>
              <th className="p-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {sortedMovies.map((movie) => (
              <tr key={movie.id} className="border-t hover:bg-gray-50 cursor-pointer" onClick={() => handleMovieClick(movie.id)}>
                <td className="p-2">
                  <div className="font-medium text-blue-600 hover:underline">{movie.title}</div>
                </td>
                <td className="p-2">{movie.year || "-"}</td>
                <td className="p-2">{movie.status || "-"}</td>
                <td className="p-2" onClick={(e) => e.stopPropagation()}>
                  <label className="inline-flex items-center">
                    <input
                      type="checkbox"
                      className="form-checkbox h-5 w-5 text-blue-600"
                      checked={movie.filtered}
                      onChange={() => handleToggle(movie.id, !movie.filtered)}
                    />
                    <span className="ml-2">Filter Profanity</span>
                  </label>
                </td>
                <td className="p-2" onClick={(e) => e.stopPropagation()}>
                  <button
                    className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleProcessMovie(movie.id);
                    }}
                    disabled={!movie.filtered || processing[movie.id]}
                  >
                    {processing[movie.id] ? "Processing..." : "Process Movie"}
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

export default MovieList;
