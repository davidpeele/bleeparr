import { useState } from 'react';

function LogViewer() {
  const [logs, setLogs] = useState([]);

  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-2">Logs</h2>
      <textarea
        className="w-full border p-2 font-mono text-sm rounded"
        rows="10"
        value={logs.join('\n')}
        readOnly
      ></textarea>
    </div>
  );
}

export default LogViewer;
