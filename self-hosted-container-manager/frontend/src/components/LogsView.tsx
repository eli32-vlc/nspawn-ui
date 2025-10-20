import React, { useEffect, useState } from 'react';

const LogsView = ({ containerId }) => {
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const response = await fetch(`/api/logs/${containerId}`);
                if (!response.ok) {
                    throw new Error('Failed to fetch logs');
                }
                const data = await response.json();
                setLogs(data.logs);
            } catch (err) {
                setError(err.message);
            } finally {
                setLoading(false);
            }
        };

        fetchLogs();
    }, [containerId]);

    if (loading) {
        return <div>Loading logs...</div>;
    }

    if (error) {
        return <div>Error: {error}</div>;
    }

    return (
        <div className="logs-view">
            <h2>Logs for Container {containerId}</h2>
            <pre>
                {logs.map((log, index) => (
                    <div key={index}>{log}</div>
                ))}
            </pre>
        </div>
    );
};

export default LogsView;