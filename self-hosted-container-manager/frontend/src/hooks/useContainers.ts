import { useEffect, useState } from 'react';

interface Container {
  id: string;
  name: string;
  status: string;
  ip: string;
}

const useContainers = () => {
  const [containers, setContainers] = useState<Container[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const fetchContainers = async () => {
    try {
      const response = await fetch('/api/containers');
      if (!response.ok) {
        throw new Error('Failed to fetch containers');
      }
      const data = await response.json();
      setContainers(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchContainers();
  }, []);

  return { containers, loading, error };
};

export default useContainers;