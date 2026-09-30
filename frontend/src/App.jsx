import { useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, Navigate } from 'react-router-dom';
import ShowList from './components/ShowList';
import SeriesDetail from './components/SeriesDetail';
import SeasonDetail from './components/SeasonDetail';
import EpisodeFiles from './components/EpisodeFiles';
import MovieList from './components/MovieList';
import MovieFiles from './components/MovieFiles';
import SettingsPanel from './components/SettingsPanel';
import Dashboard from './components/Dashboard';
import AdminPanel from './components/AdminPanel';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <Router>
      <div className="app container mx-auto px-4 py-6 max-w-6xl">
        <header className="mb-6">
          <h1 className="text-3xl font-bold mb-2">Bleeparr 2.0</h1>
          <p className="text-gray-600">Automated Profanity Detection and Censorship Tool</p>
        </header>

        {/* Navigation Tabs */}
        <nav className="mb-6">
          <ul className="flex border-b">
            <li className="mr-1">
              <Link
                to="/"
                className={`py-2 px-4 font-medium block ${
                  activeTab === 'dashboard'
                    ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                    : 'text-gray-500 hover:text-blue-500'
                }`}
                onClick={() => setActiveTab('dashboard')}
              >
                Dashboard
              </Link>
            </li>
            <li className="mr-1">
              <Link
                to="/shows"
                className={`py-2 px-4 font-medium block ${
                  activeTab === 'shows'
                    ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                    : 'text-gray-500 hover:text-blue-500'
                }`}
                onClick={() => setActiveTab('shows')}
              >
                TV Shows
              </Link>
            </li>
            <li className="mr-1">
              <Link
                to="/movies"
                className={`py-2 px-4 font-medium block ${
                  activeTab === 'movies'
                    ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                    : 'text-gray-500 hover:text-blue-500'
                }`}
                onClick={() => setActiveTab('movies')}
              >
                Movies
              </Link>
            </li>
            <li className="mr-1">
              <Link
                to="/settings"
                className={`py-2 px-4 font-medium block ${
                  activeTab === 'settings'
                    ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                    : 'text-gray-500 hover:text-blue-500'
                }`}
                onClick={() => setActiveTab('settings')}
              >
                Settings
              </Link>
            </li>
            <li className="mr-1">
              <Link
                to="/admin"
                className={`py-2 px-4 font-medium block ${
                  activeTab === 'admin'
                    ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                    : 'text-gray-500 hover:text-blue-500'
                }`}
                onClick={() => setActiveTab('admin')}
              >
                Admin
              </Link>
            </li>
          </ul>
        </nav>

        {/* Content Area */}
        <main className="bg-gray-50 p-6 border rounded-md">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/shows" element={<ShowList />} />
            <Route path="/series/:seriesId" element={<SeriesDetail />} />
            <Route path="/series/:seriesId/season/:seasonId" element={<SeasonDetail />} />
            <Route path="/series/:seriesId/season/:seasonId/episode/:episodeId" element={<EpisodeFiles />} />
            <Route path="/movies" element={<MovieList />} />
            <Route path="/movies/:movieId" element={<MovieFiles />} />
            <Route path="/settings" element={<SettingsPanel />} />
            <Route path="/admin" element={<AdminPanel />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>

        {/* Footer */}
        <footer className="mt-8 text-center text-gray-500 text-sm">
          <p>Bleeparr 2.0 &copy; {new Date().getFullYear()} - Automatic Profanity Detection and Censorship Tool</p>
          <p className="mt-1">
            <a 
              href="https://github.com/davidpeele/bleeparr" 
              target="_blank" 
              rel="noopener noreferrer"
              className="text-blue-500 hover:underline"
            >
              GitHub Repository
            </a>
          </p>
        </footer>
      </div>
    </Router>
  );
}

export default App;
