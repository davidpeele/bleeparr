import { useState, useEffect } from 'react';
import EpisodeList from './EpisodeList';

function SeasonList({ showId, showTitle, onBack }) {
  const [seasons, setSeasons] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selectedSeason, setSelectedSeason] = useState(null);
  const [episodes, setEpisodes] = useState([]);
  const [processing, setProcessing] = useState({});

  // Fetch episodes for the show
  useEffect(() => {
    setLoading(true);
    fetch(`/api/shows/${showId}/episodes`)
      .then((res) => {
        if (!res.ok) throw new Error("Failed to fetch episodes");
        return res.json();
      })
      .then((episodeData) => {
        // Group episodes by season
        const episodesBySeason = episodeData.reduce((acc, episode) => {
          const season = episode.seasonNumber;
          if (!acc[season]) {
            acc[season] = [];
          }
          acc[season].push(episode);
          return acc;
        }, {});
        
        // Convert to array and sort
        const seasonList = Object.keys(episodesBySeason)
          .map((season) => ({
            seasonNumber: parseInt(season, 10),
            episodes: episodesBySeason[season],
            episodeCount: episodesBySeason[season].length,
            hasFile: episodesBySeason[season].some(ep => ep.hasFile)
          }))
          .sort((a, b) => a.seasonNumber - b.seasonNumber);
        
        setSeasons(seasonList);
        setEpisodes(episodeData);
        setLoading(false);
      })
      .catch((err) => {
        console.error("Error fetching episodes:", err);
        setError("Failed to load episodes for this show.");
        setLoading(false);
      });
  }, [showId]);

  const handleProcessSeason = (seasonNumber) => {
    setProcessing(prev => ({ ...prev, [seasonNumber]: true }));
    
    // Get episode IDs for this season that have files
    const episodesToProcess = episodes
      .filter(ep => ep.seasonNumber === seasonNumber && ep.hasFile)
      .map(ep => ep.id);
      
    if (episodesToProcess.length === 0) {
      alert("No episodes with files found for this season.");
      setProcessing(prev => ({ ...prev, [seasonNumber]: false }));
      return;
    }
    
    // Process each episode
    const processPromises = episodesToProcess.map(episodeId => 
      fetch(`/api/process/episode/${episodeId}`, { method: "POST" })
        .then(res => {
          if (!res.ok) throw new Error(`Failed to process episode ${episodeId}`);
          return res.json();
        })
    );
    
    // Wait for all episodes to be queued
    Promise.all(processPromises)
      .then(() => {
        alert(`Processing ${episodesToProcess.length} episodes from Season ${seasonNumber}.`);
      })
      .catch(err => {
        console.error("Error processing season:", err);
        alert("Failed to process some episodes. See console for details.");
      })
      .finally(() => {
        setProcessing(prev => ({ ...prev, [seasonNumber]: false }));
      });
  };

  // If a season is selected, show episode list
  if (selectedSeason !== null) {
    return (
      <EpisodeList 
        showId={showId}
        showTitle={showTitle}
        seasonNumber={selectedSeason}
        episodes={episodes.filter(ep => ep.seasonNumber === selectedSeason)}
        onBack={() => setSelectedSeason(null)}
      />
    );
  }

  return (
    <div className="mt-6">
      <div className="flex items-center mb-4">
        <button 
          onClick={onBack}
          className="mr-2 px-3 py-1 bg-gray-200 hover:bg-gray-300 rounded-md flex items-center"
        >
          <svg className="w-4 h-4 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" d="M15 19l-7-7 7-7"></path>
          </svg>
          Back to Shows
        </button>
        <h2 className="text-xl font-semibold">{showTitle} - Seasons</h2>
      </div>
      
      {loading ? (
        <p>Loading seasons...</p>
      ) : error ? (
        <p className="text-red-500">{error}</p>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Season</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Episodes</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {seasons.map((season) => (
                <tr key={season.seasonNumber} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button 
                      onClick={() => setSelectedSeason(season.seasonNumber)}
                      className="text-blue-600 hover:underline font-medium"
                    >
                      Season {season.seasonNumber}
                    </button>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {season.episodeCount} episodes
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {season.hasFile ? (
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                        Has Files
                      </span>
                    ) : (
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                        No Files
                      </span>
                    )}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleProcessSeason(season.seasonNumber)}
                      disabled={!season.hasFile || processing[season.seasonNumber]}
                      className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50 mr-2"
                    >
                      {processing[season.seasonNumber] ? "Processing..." : "Process Season"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default SeasonList;
