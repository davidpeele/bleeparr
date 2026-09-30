import { useState } from 'react';
import ShowList from './components/ShowList';
import SettingsPanel from './components/SettingsPanel';
import Dashboard from './components/Dashboard';
import './index.css';

function App() {
  const [activeTab, setActiveTab] = useState('dashboard');

  return (
    <div className="app container mx-auto px-4 py-6 max-w-6xl">
      <header className="mb-6">
        <h1 className="text-3xl font-bold mb-2">Bleeparr 2.0</h1>
        <p className="text-gray-600">Automated Profanity Detection and Censorship Tool</p>
      </header>

      {/* Navigation Tabs */}
      <nav className="mb-6">
        <ul className="flex border-b">
          <li className="mr-1">
            <button
              className={`py-2 px-4 font-medium ${
                activeTab === 'dashboard'
                  ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                  : 'text-gray-500 hover:text-blue-500'
              }`}
              onClick={() => setActiveTab('dashboard')}
            >
              Dashboard
            </button>
          </li>
          <li className="mr-1">
            <button
              className={`py-2 px-4 font-medium ${
                activeTab === 'shows'
                  ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                  : 'text-gray-500 hover:text-blue-500'
              }`}
              onClick={() => setActiveTab('shows')}
            >
              TV Shows
            </button>
          </li>
          <li className="mr-1">
            <button
              className={`py-2 px-4 font-medium ${
                activeTab === 'settings'
                  ? 'border-l border-t border-r rounded-t bg-white text-blue-600'
                  : 'text-gray-500 hover:text-blue-500'
              }`}
              onClick={() => setActiveTab('settings')}
            >
              Settings
            </button>
          </li>
        </ul>
      </nav>

      {/* Content Area */}
      <main className="bg-gray-50 p-6 border rounded-md">
        {activeTab === 'dashboard' && <Dashboard />}
        {activeTab === 'shows' && <ShowList />}
        {activeTab === 'settings' && <SettingsPanel />}
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
  );
}

export default App;
