import React, { useState } from 'react';

const NetworkConfigForm = () => {
    const [ipv4Address, setIpv4Address] = useState('');
    const [ipv6Address, setIpv6Address] = useState('');
    const [networkName, setNetworkName] = useState('');

    const handleSubmit = (event) => {
        event.preventDefault();
        // Handle the form submission logic here
        console.log('Network Configuration:', { ipv4Address, ipv6Address, networkName });
    };

    return (
        <form onSubmit={handleSubmit}>
            <div className="form-group">
                <label htmlFor="networkName">Network Name</label>
                <input
                    type="text"
                    className="form-control"
                    id="networkName"
                    value={networkName}
                    onChange={(e) => setNetworkName(e.target.value)}
                    required
                />
            </div>
            <div className="form-group">
                <label htmlFor="ipv4Address">IPv4 Address</label>
                <input
                    type="text"
                    className="form-control"
                    id="ipv4Address"
                    value={ipv4Address}
                    onChange={(e) => setIpv4Address(e.target.value)}
                    required
                />
            </div>
            <div className="form-group">
                <label htmlFor="ipv6Address">IPv6 Address</label>
                <input
                    type="text"
                    className="form-control"
                    id="ipv6Address"
                    value={ipv6Address}
                    onChange={(e) => setIpv6Address(e.target.value)}
                />
            </div>
            <button type="submit" className="btn btn-primary">Configure Network</button>
        </form>
    );
};

export default NetworkConfigForm;