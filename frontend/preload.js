// ============================================================================
//  File: preload.js
//  Version: 1.00
//  Purpose: Electron preload script for context bridge
//  Created: 28JUL25
// ============================================================================
// SECTION 1: Global Variable Definitions
// ============================================================================

const { contextBridge, ipcRenderer } = require('electron');

// ============================================================================
// SECTION 2: Context Bridge Exposition
// ============================================================================

contextBridge.exposeInMainWorld('electronAPI', {
    invokeAgentTask: (payload) => ipcRenderer.invoke('agent-task', payload)
});
//
//
//End Of Script
