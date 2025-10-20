import React, { useEffect, useState } from 'react';
import { Container } from 'react-bootstrap';
import { fetchContainers } from '../hooks/useContainers';

const ContainerList: React.FC = () => {
    const [containers, setContainers] = useState<any[]>([]);
    const [loading, setLoading] = useState<boolean>(true);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const loadContainers = async () => {
            try {
                const data = await fetchContainers();
                setContainers(data);
            } catch (err) {
                setError('Failed to load containers');
            } finally {
                setLoading(false);
            }
        };

        loadContainers();
    }, []);

    if (loading) {
        return <div>Loading...</div>;
    }

    if (error) {
        return <div>{error}</div>;
    }

    return (
        <Container>
            <h2>Container List</h2>
            <table className="table">
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Status</th>
                        <th>IP Address</th>
                    </tr>
                </thead>
                <tbody>
                    {containers.map((container) => (
                        <tr key={container.name}>
                            <td>{container.name}</td>
                            <td>{container.status}</td>
                            <td>{container.ip}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </Container>
    );
};

export default ContainerList;