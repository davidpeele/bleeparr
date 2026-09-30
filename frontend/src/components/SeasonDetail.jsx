// frontend/src/components/SeasonDetail.jsx
import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import EpisodeList from './EpisodeList';

function SeasonDetail() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [series, setSeries] = useState(null);
  
  const { seriesId, seasonId } = useParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchEpisodes();
  }, [seriesId, seasonId]);
  
  const fetchEpisodes = async () => {
    setLoading(true);
    try {
      // First get the series info to get the title
      const seriesResponse = await fetch(`/api/shows/${seriesId}`);
      if (!seriesResponse.ok) {
        throw new Error(`Failed to fetch series: ${seriesResponse.statusText}`);
      }
      const seriesData = await seriesResponse.json();
      setSeries(seriesData);
      
      // Then get episodes for this specific season
      const episodesResponse = await fetch(`/api/shows/${seriesId}/episodes`);
      if (!episodesResponse.ok) {
        throw new Error(`Failed to fetch episodes: ${episodesResponse.statusText}`);
      }
      
      const allEpisodes = await episodesResponse.json();
      
      // Filter to only episodes from this season
      const seasonEpisodes = allEpisodes.filter(
        episode => episode.seasonNumber === parseInt(seasonId, 10)
      );
      
      setEpisodes(seasonEpisodes);
      setError(null);
    } catch (err) {
      console.error('Error fetching episodes:', err);
      setError('Failed to load episodes. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const handleBack = () => {
    navigate(`/series/${seriesId}`);
  };
  
  if (loading) {
    return <div className="p-4">Loading episodes...</div>;
  }
  
  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-4">{error}</div>
        <button 
          onClick={handleBack}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          Go Back to Series
        </button>
      </div>
    );
  }
  
  return (
    <EpisodeList
      showId={seriesId}
      showTitle={series?.title || 'Unknown Series'}
      seasonNumber={seasonId}
      episodes={episodes}
      onBack={handleBack}
    />
  );
}

export default SeasonDetail;