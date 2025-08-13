// ============================================================================
//  File: renderer.js
//  Version: 1.00
//  Purpose: Electron renderer (React UI) for Gemini-Agent
//  Created: 28JUL25
// ============================================================================
// SECTION 1: Global Variable Definitions
// ============================================================================

const React = require('react');
const ReactDOM = require('react-dom');

// ============================================================================
// SECTION 2: Main React App Component
// ============================================================================

function App() {
    // Banner: Main React UI for Gemini-Agent
    const [output, setOutput] = React.useState('');
    const [task, setTask] = React.useState('');
    const [agent, setAgent] = React.useState('codegen');
    const [status, setStatus] = React.useState('idle');
    const [error, setError] = React.useState('');
    const [apiKey, setApiKey] = React.useState('');
    const [progress, setProgress] = React.useState(0);
    const [choices, setChoices] = React.useState([]);
    const [clarify, setClarify] = React.useState('');

    // Banner: Handler for sending agent task to backend
    const handleSend = () => {
        setStatus('Running...');
        setError(null);
        setOutput('');
        setProgress(0);
        setChoices([]);
        setClarify('');
        try {
            const ws = new window.WebSocket('ws://localhost:9102/ws');
            ws.onopen = () => {
                ws.send(JSON.stringify({ agent, task, llm_api_key: apiKey }));
            };
            ws.onmessage = (event) => {
    // Streaming protocol: handle plain string messages
    const msg = typeof event.data === 'string' ? event.data : '';
    if (msg.startsWith('STREAM_CHUNK:')) {
        // Format: STREAM_CHUNK:agent_name:chunk
        const firstColon = msg.indexOf(':');
        const secondColon = msg.indexOf(':', firstColon+1);
        const agentName = msg.substring(firstColon+1, secondColon);
        const chunk = msg.substring(secondColon+1);
        setOutput(prev => prev + chunk);
        setStatus('Streaming...');
        setProgress(p => Math.min(p + 5, 95));
    } else if (msg.startsWith('AGENT_START:')) {
        // Format: AGENT_START:agent_name
        setOutput('');
        setStatus('Streaming...');
        setProgress(0);
    } else if (msg.startsWith('AGENT_COMPLETE:')) {
        setStatus('Done');
        setProgress(100);
    } else if (msg.startsWith('[ERROR]')) {
        setError(msg);
        setStatus('Error');
    } else {
        // Fallback: old protocol or JSON
        try {
            const data = JSON.parse(event.data);
            if (data.chunk) {
                setOutput(prev => prev + (prev ? '\n' : '') + data.chunk);
                setStatus('Streaming...');
                setProgress(p => Math.min(p + 5, 95));
                if (data.chunk.startsWith('[CLARIFY]')) {
                    setClarify(data.chunk.replace('[CLARIFY]', '').trim());
                }
                if (data.chunk.startsWith('[CHOICES]')) {
                    const opts = data.chunk.replace('[CHOICES]', '').split(';').map(s => s.trim()).filter(Boolean);
                    setChoices(opts);
                }
            }
            if (data.error) {
                setError(data.error);
                setStatus('Error');
                ws.close();
            }
        } catch {}
    }
};
            ws.onclose = () => {
                setStatus(s => s === 'Streaming...' ? 'Done' : s);
                setProgress(100);
            };
            ws.onerror = (e) => {
                setError('WebSocket error');
                setStatus('Error');
            };
        } catch (e) {
            setError(String(e));
            setStatus('Error');
        }
    };

    const [showSettings, setShowSettings] = React.useState(false);
    return (
        <div className="App">
            <h1>Gemini-Agent</h1>
            <button onClick={()=>setShowSettings(true)}>Settings</button>
            <SettingsModal show={showSettings} onClose={()=>setShowSettings(false)}/>
            <div>
                <label>Agent:</label>
                <select value={agent} onChange={e => setAgent(e.target.value)}>
                    <option value="codegen">CodeGen</option>
                    <option value="qa">QA</option>
                    <option value="test">Test</option>
                    <option value="fix">Fix</option>
                    <option value="planner">Planner</option>
                    <option value="doc">Document</option>
                </select>
                <input
                    type="text"
                    placeholder="Enter your task..."
                    value={task}
                    onChange={e => setTask(e.target.value)}
                />
                <button onClick={handleSend} disabled={status==='Running...' || !task}>Send Task</button>
            </div>
            <div style={{marginTop:8}}>
                {status==='Running...' || status==='Streaming...'
                    ? <div><span className="spinner"/> <span>{status}</span></div>
                    : null}
                <progress value={progress} max="100" style={{width: '100%'}} />
            </div>
            {clarify && <div className="clarify">Agent asks: {clarify}</div>}
            {choices.length > 0 && (
                <div className="choices">
                    {choices.map((c,i)=>(<button key={i} onClick={()=>setTask(c)}>{c}</button>))}
                </div>
            )}
            <div>Status: {status}</div>
            {error && <div className="error">Error: {error}</div>}
            <pre style={{background:'#222',color:'#b5f',padding:8,overflowX:'auto'}} dangerouslySetInnerHTML={{__html:window.hljs?.highlightAuto(output).value||output}} />
        </div>
    );
}

// ============================================================================
// SECTION 3: Render App
// ============================================================================

ReactDOM.render(
    React.createElement(App, null, null),
    document.getElementById('root')
);
//
//
//End Of Script`
