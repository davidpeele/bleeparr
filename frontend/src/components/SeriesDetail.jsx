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
      
      console.log('Series data structure:', seriesData); // Log for debugging
      
      let seasonData = [];
      
      // Depending on the API response format:
      if (seriesData.seasons) {
        // Option 1: seriesData.seasons contains season objects with episodeCount
        if (seriesData.seasons.length > 0 && 'statistics' in seriesData.seasons[0]) {
          seasonData = seriesData.seasons
            .filter(season => season.seasonNumber > 0) // Skip specials
            .map(season => ({
              seasonNumber: season.seasonNumber,
              name: `Season ${season.seasonNumber}`,
              episodeCount: season.statistics?.episodeCount || season.statistics?.totalEpisodeCount || 0
            }))
            .sort((a, b) => a.seasonNumber - b.seasonNumber);
        } 
        // Option 2: seriesData.seasons contains episode objects grouped by seasonNumber
        else {
          const seasonNumbers = [...new Set(seriesData.seasons.map(s => s.seasonNumber))].sort((a, b) => a - b);
          
          seasonData = seasonNumbers
            .filter(num => num > 0) // Skip specials (season 0)
            .map(seasonNumber => {
              const episodesInSeason = seriesData.seasons.filter(s => s.seasonNumber === seasonNumber);
              return {
                seasonNumber,
                name: `Season ${seasonNumber}`,
                episodeCount: episodesInSeason.length
              };
            });
        }
      }
      // Option 3: We need to fetch episodes separately
      else if (seriesData.id) {
        // Fetch episodes
        const episodesResponse = await fetch(`/api/shows/${seriesId}/episodes`);
        if (episodesResponse.ok) {
          const episodes = await episodesResponse.json();
          // Group by season
          const seasonMap = {};
          episodes.forEach(ep => {
            if (ep.seasonNumber > 0) { // Skip specials
              if (!seasonMap[ep.seasonNumber]) {
                seasonMap[ep.seasonNumber] = [];
              }
              seasonMap[ep.seasonNumber].push(ep);
            }
          });
          
          // Create seasons array
          seasonData = Object.keys(seasonMap).map(seasonNumber => ({
            seasonNumber: parseInt(seasonNumber, 10),
            name: `Season ${seasonNumber}`,
            episodeCount: seasonMap[seasonNumber].length
          })).sort((a, b) => a.seasonNumber - b.seasonNumber);
        }
      }
      
      setSeasons(seasonData);
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
