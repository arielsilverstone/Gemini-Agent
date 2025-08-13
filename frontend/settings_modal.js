// ============================================================================
//  File: settings_modal.js
//  Version: 1.00
//  Purpose: React modal for config editing, hot-reload, and validation
//  Created: 29JUL25
// ============================================================================

import React, { useState, useEffect } from 'react';

// ============================================================================
//  Main Component
// ============================================================================


export default function SettingsModal({ show, onClose }) {
    const [config, setConfig] = useState(null);
    const [error, setError] = useState('');
    const [saving, setSaving] = useState(false);
    useEffect(() => {
        if (show) {
            fetch('/api/get_config').then(r=>r.json()).then(setConfig).catch(e=>setError(String(e)));
        }
    }, [show]);
    const handleSave = () => {
        setSaving(true);
        fetch('/api/save_config', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify(config)
        })
        .then(r=>r.json())
        .then(r=>{
            setSaving(false);
            if(r.status!=='ok') setError(r.error||'Failed to save');
            else onClose();
        })
        .catch(e=>{setError(String(e));setSaving(false);});
    };
    if(!show) return null;
    return (
        <div className="modal">
            <h2>Settings</h2>
            {error && <div className="error">{error}</div>}
            {config && Object.keys(config).map(k=>(
                <div key={k}><label>{k}</label><input value={config[k]} onChange={e=>setConfig({...config,[k]:e.target.value})}/></div>
            ))}
            <button onClick={handleSave} disabled={saving}>Save</button>
            <button onClick={onClose}>Cancel</button>
        </div>
    );
}
//
//
//End Of Script
