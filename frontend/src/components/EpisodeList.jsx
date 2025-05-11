import { useState } from 'react';

function EpisodeList({ showId, showTitle, seasonNumber, episodes, onBack }) {
  const [processing, setProcessing] = useState({});

  const handleProcessEpisode = (episodeId) => {
    setProcessing(prev => ({ ...prev, [episodeId]: true }));
    
    fetch(`/api/process/episode/${episodeId}`, { method: "POST" })
      .then((res) => {
        if (!res.ok) throw new Error("Failed to process episode");
        return res.json();
      })
      .then((data) => {
        alert(`Episode queued for processing.`);
      })
      .catch((err) => {
        console.error("Failed to process episode:", err);
        alert("Failed to process episode. See console for details.");
      })
      .finally(() => {
        setProcessing(prev => ({ ...prev, [episodeId]: false }));
      });
  };

  // Filter to episodes that have files
  const episodesWithFiles = episodes.filter(ep => ep.hasFile);

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
          Back to Seasons
        </button>
        <h2 className="text-xl font-semibold">{showTitle} - Season {seasonNumber}</h2>
      </div>
      
      {episodesWithFiles.length === 0 ? (
        <p>No episodes with files found for this season.</p>
      ) : (
        <div className="bg-white border rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Episode</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Title</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Air Date</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {episodesWithFiles.map((episode) => (
                <tr key={episode.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    Episode {episode.episodeNumber}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {episode.title}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    {episode.airDate ? new Date(episode.airDate).toLocaleDateString() : "Unknown"}
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <button
                      onClick={() => handleProcessEpisode(episode.id)}
                      disabled={processing[episode.id]}
                      className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50"
                    >
                      {processing[episode.id] ? "Processing..." : "Process Episode"}
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

export default EpisodeList;
