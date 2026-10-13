import React from 'react';

function Footer() {
    return (
        <footer style={{ padding: '20px', marginTop: '20px', textAlign: 'center', backgroundColor: '#003366', color: 'white' }}>
            <p>Copyright © {new Date().getFullYear()} Politecnico di Torino.</p>
            <p>Address: Corso Duca Degli Abruzzi 24, 10129 Torino, Italy</p>
        </footer>
    );
}

export default Footer;