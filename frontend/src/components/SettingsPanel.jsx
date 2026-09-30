function SettingsPanel() {
  return (
    <div className="mb-6">
      <h2 className="text-xl font-semibold mb-2">Settings</h2>
      <form className="space-y-3">
        <div>
          <label className="block font-medium">Sonarr API URL</label>
          <input type="text" placeholder="http://localhost:8989" className="w-full border px-3 py-2 rounded" />
        </div>
        <div>
          <label className="block font-medium">API Key</label>
          <input type="text" placeholder="Your Sonarr API Key" className="w-full border px-3 py-2 rounded" />
        </div>
        <div>
          <label className="block font-medium">Swears File Path</label>
          <input type="text" placeholder="swears.txt" className="w-full border px-3 py-2 rounded" />
        </div>
        <button type="submit" className="px-4 py-2 bg-blue-600 text-white rounded">Save</button>
      </form>
    </div>
  );
}

export default SettingsPanel;
