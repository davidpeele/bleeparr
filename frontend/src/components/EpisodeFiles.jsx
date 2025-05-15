import { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';

function EpisodeFiles() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [fileData, setFileData] = useState({
    series_title: '',
    season: 0,
    episode: 0,
    files: []
  });
  const [processing, setProcessing] = useState({});
  
  const { seriesId, seasonId, episodeId } = useParams();
  const navigate = useNavigate();
  
  useEffect(() => {
    fetchFiles();
  }, [seriesId, seasonId, episodeId]);
  
  const fetchFiles = async () => {
    setLoading(true);
    try {
      const url = `/api/episodes/${seriesId}/${seasonId}/files${episodeId ? `?episode_id=${episodeId}` : ''}`;
      const response = await fetch(url);
      
      if (!response.ok) {
        throw new Error(`Failed to fetch files: ${response.statusText}`);
      }
      
      const data = await response.json();
      setFileData(data);
      setError(null);
    } catch (err) {
      console.error('Error fetching files:', err);
      setError('Failed to load files. Please try again.');
    } finally {
      setLoading(false);
    }
  };
  
  const formatFileSize = (bytes) => {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
  };
  
  const handleProcessFile = async (filePath) => {
    setProcessing(prev => ({ ...prev, [filePath]: true }));
    
    try {
      const response = await fetch('/api/files/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ file_path: filePath })
      });
      
      if (!response.ok) {
        throw new Error('Failed to process file');
      }
      
      const data = await response.json();
      alert(data.message);
    } catch (err) {
      console.error('Error processing file:', err);
      alert('Failed to process file. See console for details.');
    } finally {
      setProcessing(prev => ({ ...prev, [filePath]: false }));
    }
  };
  
  const handleBack = () => {
    // Navigate back based on context
    if (episodeId) {
      navigate(`/series/${seriesId}/season/${seasonId}`);
    } else if (seasonId) {
      navigate(`/series/${seriesId}`);
    } else {
      navigate('/shows');
    }
  };
  
  if (loading) {
    return <div className="p-4">Loading files...</div>;
  }
  
  if (error) {
    return (
      <div className="p-4">
        <div className="text-red-500 mb-4">{error}</div>
        <button 
          onClick={handleBack}
          className="px-4 py-2 bg-blue-500 text-white rounded"
        >
          Go Back
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
        
        <h2 className="text-xl font-semibold">
          {fileData.series_title} - 
          Season {fileData.season}
          {fileData.episode && ` - Episode ${fileData.episode}`}
        </h2>
      </div>
      
      <div className="text-sm text-gray-600 mb-4">
        Directory: {fileData.directory}
      </div>
      
      {fileData.files.length === 0 ? (
        <div className="bg-yellow-50 p-4 border border-yellow-200 rounded-md">
          <p className="text-yellow-700">No video files found in this directory.</p>
        </div>
      ) : (
        <div className="bg-white rounded-lg shadow overflow-hidden">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Filename</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Size</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200">
              {fileData.files.map((file, index) => (
                <tr key={index} className={index % 2 === 0 ? 'bg-white' : 'bg-gray-50'}>
                  <td className="px-4 py-3 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{file.name}</div>
                    <div className="text-xs text-gray-500">{file.path}</div>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                    {formatFileSize(file.size)}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">
                    {file.is_processed ? (
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-green-100 text-green-800">
                        Processed
                      </span>
                    ) : (
                      <span className="px-2 inline-flex text-xs leading-5 font-semibold rounded-full bg-gray-100 text-gray-800">
                        Original
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap text-sm">
                    <button
                      onClick={() => handleProcessFile(file.path)}
                      disabled={processing[file.path] || file.is_processed}
                      className="px-3 py-1 bg-blue-500 text-white rounded-md text-sm hover:bg-blue-600 disabled:opacity-50"
                    >
                      {processing[file.path] ? "Processing..." : "Process File"}
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

export default EpisodeFiles;
