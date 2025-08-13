// ============================================================================
//  File: streaming_ui.js
//  Version: 1.00
//  Purpose: Standalone multi-agent streaming WebSocket UI for Gemini-Agent
//  Created: 29JUL25
// ============================================================================

// Connect to backend WebSocket
const websocket = new WebSocket('ws://localhost:9102/ws');

// Get or create output area for an agent
function getOrCreateAgentOutputDiv(agentName) {
    const container = document.getElementById('outputContainer');
    let agentDiv = document.getElementById(`output-${agentName}`);
    if (!agentDiv) {
        agentDiv = document.createElement('div');
        agentDiv.id = `output-${agentName}`;
        agentDiv.classList.add('agent-output-section');
        const agentHeader = document.createElement('h3');
        agentHeader.textContent = `${agentName} Output:`;
        agentDiv.appendChild(agentHeader);
        const agentContent = document.createElement('pre');
        agentContent.id = `content-${agentName}`;
        agentContent.classList.add('agent-content');
        agentDiv.appendChild(agentContent);
        container.appendChild(agentDiv);
    }
    return document.getElementById(`content-${agentName}`);
}
// ============================================================================
//  WebSocket message handler
// ============================================================================
websocket.onmessage = function(event) {
    const message = event.data;
    // --- AGENT_START ---
    if (message.startsWith("AGENT_START:")) {
        const agentName = message.split(':')[1];
        const outputElement = getOrCreateAgentOutputDiv(agentName);
        outputElement.textContent = `[${agentName}] Starting... \n`;
        outputElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    // --- STREAM_CHUNK ---
    else if (message.startsWith("STREAM_CHUNK:")) {
        const firstColon = message.indexOf(':');
        const secondColon = message.indexOf(':', firstColon+1);
        const agentName = message.substring(firstColon+1, secondColon);
        const chunk = message.substring(secondColon+1);
        const outputElement = getOrCreateAgentOutputDiv(agentName);
        outputElement.textContent += chunk;
        outputElement.scrollTop = outputElement.scrollHeight;
    }
    // --- AGENT_COMPLETE ---
    else if (message.startsWith("AGENT_COMPLETE:")) {
        const agentName = message.split(':')[1];
        const outputElement = getOrCreateAgentOutputDiv(agentName);
        outputElement.textContent += `\n[${agentName}] Task Complete.\n`;
        outputElement.scrollIntoView({ behavior: 'smooth', block: 'end' });
    }
    // --- ORCHESTRATOR / ERROR ---
    else if (message.startsWith("[ORCHESTRATOR]")) {
        const statusArea = document.getElementById('orchestratorStatus');
        if (statusArea) {
            statusArea.textContent += message + '\n';
            statusArea.scrollTop = statusArea.scrollHeight;
        }
    }
    else if (message.startsWith("[ERROR]")) {
        const errorArea = document.getElementById('errorDisplayArea') || document.getElementById('orchestratorStatus');
        if (errorArea) {
            errorArea.textContent += message + '\n';
            errorArea.scrollTop = errorArea.scrollHeight;
            errorArea.style.color = 'red';
        }
    }
    else {
        // Unhandled message
        console.log("Unhandled message type:", message);
    }
};

// ============================================================================
//  Example workflow trigger (adjust as needed)
// ============================================================================
document.getElementById('startWorkflowButton').onclick = function() {
    const workflowName = document.getElementById('workflowNameInput').value;
    const initialTask = document.getElementById('initialTaskInput').value;
    websocket.send(`START_WORKFLOW:${workflowName}:${initialTask}`);
};

// Ensure these HTML elements exist:
// <div id="outputContainer"></div>
// <div id="orchestratorStatus"></div>
// <div id="errorDisplayArea"></div>
// <input id="workflowNameInput"/>
// <input id="initialTaskInput"/>
// <button id="startWorkflowButton">Start Workflow</button>
//
//
//End Of Script
