import { useEffect, useState } from 'react';
import ShowList from './ShowList';
import SettingsPanel from './SettingsPanel';
import LogViewer from './LogViewer';
import './styles/main.css';

function App() {
  const [shows, setShows] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/api/shows")
      .then(res => res.json())
      .then(data => {
        setShows(data);
        setLoading(false);
      });
  }, []);

  return (
    <div className="app p-4">
      <h1 className="text-2xl font-bold mb-4">Bleeparr 2.0</h1>
      <SettingsPanel />
      {loading ? <p>Loading shows...</p> : <ShowList shows={shows} />}
      <LogViewer />
    </div>
  );
}

export default App;
