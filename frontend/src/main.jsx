import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App.jsx';

// Mount the App component to the HTML element with the ID 'root'
ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);