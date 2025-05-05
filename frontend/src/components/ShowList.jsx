function ShowList({ shows }) {
  return (
    <div className="mt-6">
      <h2 className="text-xl font-semibold mb-2">TV Shows</h2>
      <table className="min-w-full border border-gray-200">
        <thead>
          <tr className="bg-gray-100">
            <th className="p-2 text-left">Title</th>
            <th className="p-2 text-left">Monitored</th>
          </tr>
        </thead>
        <tbody>
          {shows.map(show => (
            <tr key={show.id} className="border-t">
              <td className="p-2">{show.title}</td>
              <td className="p-2">
                <input type="checkbox" defaultChecked={show.monitored} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default ShowList;
