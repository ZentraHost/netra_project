/**
 * NETRA - Main Entry Point
 * Orchestrates the modules.
 */

import { CONFIG, STATE } from './config.js';
import { UI, showFeedback, updateStatus } from './ui.js';
import { connectWS, sendFrame } from './network.js';
import { setupInputs } from './input.js';

// Initialize Inputs 
// (Wait for DOM load if using <script type="module"> in head, 
// but usually put at end of body. Modules defer by default anyway.)
setupInputs();

// Global Access for Debugging
window.NETRA = { STATE, CONFIG, UI };

// --- System Control ---

export async function toggleSystem() {
    if (STATE.active) {
        stopSystem();
    } else {
        await startSystem();
    }
}

async function startSystem() {
    if (window.spatialAudio) window.spatialAudio.init();

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { 
                facingMode: { ideal: 'environment' }, 
                width: { ideal: 1280 } 
            }
        });
        
        UI.cam.srcObject = stream;
        await new Promise(resolve => UI.cam.onloadedmetadata = resolve);
        
        STATE.active = true;
        UI.body.classList.add('active');

        showFeedback('NETRA ACTIVE');
        updateStatus('Connecting...', 'active');

        connectWS();

    } catch (e) {
        console.error("Camera Error:", e);
        showFeedback('CAMERA ERROR');
        updateStatus('Cam Error', 'error');
    }
}

function stopSystem() {
    STATE.active = false;
    STATE.mode = 'nav';
    STATE.wsRetryCount = 0;
    
    if (window.spatialAudio) window.spatialAudio.stopMicroTone();
    UI.body.classList.remove('active');

    // Close WS
    if (STATE.ws) {
        STATE.ws.onclose = null;
        STATE.ws.close();
        STATE.ws = null;
    }
    
    // Stop Loop
    stopLoop();

    // Stop Camera
    if (UI.cam.srcObject) {
        UI.cam.srcObject.getTracks().forEach(track => track.stop());
        UI.cam.srcObject = null;
    }

    showFeedback('STOPPED');
    updateStatus('Ready', '');
}

// --- Loop Logic ---

export function startLoop() {
    if (STATE.loop) clearInterval(STATE.loop);
    STATE.loop = setInterval(tick, CONFIG.scanInterval);
}

export function startMicroLoop() {
    if (STATE.loop) clearInterval(STATE.loop);
    STATE.loop = setInterval(tick, CONFIG.microInterval);
}

function stopLoop() {
    if (STATE.loop) clearInterval(STATE.loop);
    STATE.loop = null;
}

function tick() {
    if (!STATE.active || !STATE.ws || STATE.ws.readyState !== WebSocket.OPEN) return;

    const cvs = document.createElement('canvas');
    const ratio = UI.cam.videoHeight / UI.cam.videoWidth;
    cvs.width = CONFIG.imgWidth;
    cvs.height = Math.round(CONFIG.imgWidth * ratio);

    const ctx = cvs.getContext('2d');
    ctx.drawImage(UI.cam, 0, 0, cvs.width, cvs.height);

    cvs.toBlob(blob => {
        sendFrame(blob);
    }, 'image/jpeg', CONFIG.jpegQuality);
}

// --- Debug Overlay ---
export function checkDebugOverlay() { 
    const box = document.getElementById('console-log');
    if (box) box.classList.toggle('visible'); 
}

// --- On-Screen Console Setup ---
(function setupConsole() {
    const box = document.getElementById('console-log');
    if (!box) return;

    const _log = console.log;
    const _err = console.error;
    
    const addItem = (msg, type) => {
        const div = document.createElement('div');
        div.className = `log-entry log-${type}`;
        div.textContent = `[${type.toUpperCase()}] ${msg}`;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    };

    console.log = (...args) => { _log(...args); addItem(args.join(' '), 'info'); };
    console.error = (...args) => { _err(...args); addItem(args.join(' '), 'error'); };
})();
