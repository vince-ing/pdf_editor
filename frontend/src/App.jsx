import React, { useState, useEffect, useCallback, useRef } from 'react';
import { engineApi } from './api/client';
import { PageRenderer } from './components/PageRenderer';

function App() {
    const [documentState, setDocumentState] = useState(null);
    const [loading, setLoading] = useState(false);
    const [documentUrl, setDocumentUrl] = useState(null);
    const fileInputRef = useRef(null); // Used to trigger the hidden file input

    const refreshDocumentState = useCallback(async () => {
        try {
            const data = await engineApi.getDocumentState();
            if (data && data.node_type === "document") {
                setDocumentState(data);
            }
        } catch (error) {
            console.error("Failed to fetch document state:", error);
        }
    }, []);

    useEffect(() => {
        refreshDocumentState();
    }, [refreshDocumentState]);

    const handleUndo = async () => {
        try {
            await engineApi.undo();
            await refreshDocumentState();
        } catch (e) {
            alert("Nothing to undo!");
        }
    };

    const handleFileUpload = async (event) => {
        const file = event.target.files[0];
        if (!file) return;

        setLoading(true);
        try {
            // 1. Create a local Object URL so the browser can render the PDF instantly
            // This bypasses the need for the backend to stream the file back!
            const localUrl = URL.createObjectURL(file);
            setDocumentUrl(localUrl);

            // 2. Send the actual file bytes to the Python engine to be parsed
            await engineApi.uploadDocument(file);
            
            // 3. Sync the Scene Graph
            await refreshDocumentState();
        } catch (error) {
            console.error(error);
            alert("Failed to upload document.");
        } finally {
            setLoading(false);
            // Reset input so you can upload the same file again if needed
            event.target.value = null; 
        }
    };

    if (loading) return <div style={{ padding: '20px' }}>Loading Engine State...</div>;

    return (
        <div style={{ display: 'flex', flexDirection: 'column', height: '100vh', backgroundColor: '#e0e0e0' }}>
            {/* Top Toolbar */}
            <div style={{ padding: '15px', backgroundColor: '#2c3e50', color: 'white', display: 'flex', gap: '15px', alignItems: 'center' }}>
                
                {/* Hidden File Input */}
                <input 
                    type="file" 
                    accept="application/pdf"
                    ref={fileInputRef}
                    style={{ display: 'none' }}
                    onChange={handleFileUpload}
                />
                
                {/* Button that triggers the hidden input */}
                <button 
                    onClick={() => fileInputRef.current.click()}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#3498db', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Open PDF File
                </button>

                <button 
                    onClick={handleUndo}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#e74c3c', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Undo Last Action
                </button>
                <button 
                    onClick={refreshDocumentState}
                    style={{ padding: '8px 16px', cursor: 'pointer', backgroundColor: '#2ecc71', color: 'white', border: 'none', borderRadius: '4px' }}
                >
                    Sync State
                </button>
                
                <span style={{ marginLeft: 'auto', fontWeight: 'bold' }}>
                    {documentState ? `Loaded: ${documentState.file_name}` : "No Document Loaded"}
                </span>
            </div>

            {/* Document Viewport */}
            <div style={{ flex: 1, overflow: 'auto', padding: '20px', display: 'flex', flexDirection: 'column' }}>
                {!documentState && (
                    <div style={{ margin: 'auto', color: '#7f8c8d' }}>
                        Click "Open PDF File" to select a document from your computer.
                    </div>
                )}
                
                {documentState && documentState.children && documentState.children.map(page => (
                    <PageRenderer 
                        key={page.id} 
                        pageNode={page} 
                        documentUrl={documentUrl} 
                    />
                ))}
            </div>
        </div>
    );
}

export default App;