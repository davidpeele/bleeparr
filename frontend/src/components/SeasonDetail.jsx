// frontend/src/components/SeriesDetail.jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';

function SeriesDetail() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [series, setSeries] = useState(null);
  const [seasons, setSeasons] = useState([]);
  
  const { seriesId } = useParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchSeriesDetails();
  }, [seriesId]);
  
  const fetchSeriesDetails = async () => {
    setLoading(true);
    try {
      // Fetch series details
      const seriesResponse = await fetch(`/api/shows/${seriesId}`);
      
      if (!seriesResponse.ok) {
        throw new Error(`Failed to fetch series: ${seriesResponse.statusText}`);
      }
      
      const seriesData = await seriesResponse.json();
      setSeries(seriesData);
      
      // Get seasons data
      const seasonsData = [];
      const seasonNumbers = [...new Set(seriesData.seasons.map(s => s.seasonNumber))].sort((a, b) => a - b);
      
      // Create seasons array
      seasonNumbers.forEach(seasonNumber => {
        // Skip season 0 (specials) if you want
        if (seasonNumber > 0) {
          seasonsData.push({
            seasonNumber,
            name: `Season ${seasonNumber}`,
            episodeCount: seriesData.seasons.filter(s => s.seasonNumber === seasonNumber).length
          });
        }
      });
      
      setSeasons(seasonsData);
      setError(null);
    } catch (err) {
      console.error('Error fetching series details:', err);
      setError('Failed to load series details. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleBack = () => {
    navigate('/shows');
  };
  
  if (loading) {
    return <div className="p-4">Loading series details...</div>;
  }
  
  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-4">{error}</div>
        <button 
          onClick={handleBack}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          Go Back to Shows
        </button>
      </div>
    );
  }
  
  if (!series) {
    return (
      <div className="p-4">
        <div className="bg-yellow-50 p-4 border border-yellow-200 rounded-md">
          <p className="text-yellow-700">Series not found.</p>
        </div>
        <button 
          onClick={handleBack}
          className="mt-4 px-4 py-2 bg-blue-500 text-white rounded"
        >
          Go Back to Shows
        </button>
      </div>
    );
  }
  
  return (
    <div className="mt-6">
      <div className="flex items-center mb-4">
        <button 
          onClick={handleBack}
          className="mr-4 px-3 py-1 bg-gray-200 rounded hover:bg-gray-300 flex items-center"
        >
          <span>←</span>
          <span className="ml-1">Back</span>
        </button>
        
        <h2 className="text-xl font-semibold">{series.title}</h2>
      </div>
      
      <div className="mb-6">
        <div className="flex">
          {series.images && series.images.length > 0 && (
            <img 
              src={series.images[0].remoteUrl} 
              alt={series.title}
              className="w-40 h-auto rounded shadow-md mr-4"
            />
          )}
          
          <div>
            {series.year && <p className="text-gray-600">Year: {series.year}</p>}
            {series.runtime && <p className="text-gray-600">Runtime: {series.runtime} min</p>}
            {series.status && <p className="text-gray-600">Status: {series.status}</p>}
            {series.network && <p className="text-gray-600">Network: {series.network}</p>}
            
            {series.overview && (
              <div className="mt-3">
                <h3 className="font-medium">Overview</h3>
                <p className="text-sm mt-1">{series.overview}</p>
              </div>
            )}
          </div>
        </div>
      </div>
      
      <h3 className="text-lg font-semibold mb-3">Seasons</h3>
      
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {seasons.map((season) => (
          <Link 
            key={season.seasonNumber}
            to={`/series/${seriesId}/season/${season.seasonNumber}`}
            className="bg-white rounded-lg shadow p-4 hover:shadow-md transition-shadow"
          >
            <div className="font-medium text-lg">{season.name}</div>
            <div className="text-gray-600 text-sm">{season.episodeCount} episodes</div>
          </Link>
        ))}
      </div>
    </div>
  );
}

export default SeriesDetail;