/**
 * NETRA - Network Manager
 * Handles WebSocket connection and message routing.
 */

import { STATE } from './config.js';
import { updateNavUI, updateMicroUI, updateTaskUI, updateInquiryUI, updateStatus, showFeedback } from './ui.js';
import { startLoop, startMicroLoop } from './main.js';

export function connectWS() {
    if (!STATE.active) return;

    const proto = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${proto}//${location.host}/ws`;
    
    STATE.ws = new WebSocket(wsUrl);

    STATE.ws.onopen = () => {
        console.log("WebSocket Connected");
        STATE.wsRetryCount = 0;
        updateStatus('Scanning', 'active');
        startLoop();
    };

    STATE.ws.onmessage = async (msg) => {
        try {
            const data = JSON.parse(msg.data);
            handleServerMessage(data);
        } catch (e) {
            console.error("JSON Parse Error:", e);
        }
    };

    STATE.ws.onclose = (e) => {
        console.warn("WebSocket Closed:", e.code);
        if (STATE.active) {
            updateStatus('Reconnecting...', 'error');
            const retryDelay = Math.min(5000, 1000 * Math.pow(1.5, STATE.wsRetryCount));
            STATE.wsRetryCount++;
            setTimeout(connectWS, retryDelay);
        }
    };
    
    STATE.ws.onerror = (e) => console.error("WebSocket Error:", e);
}

function handleServerMessage(data) {
    // Mode Switching Logic
    if (data.mode && data.mode !== STATE.mode) {
        STATE.mode = data.mode;
        
        // Mode changed -> Update Loop
        if (STATE.mode === 'micro') {
            showFeedback('MICRO MODE');
            if(window.spatialAudio) window.spatialAudio.startMicroTone();
            updateStatus('Precision', 'active');
            startMicroLoop();
        } else {
             // 'nav' or 'task'
            showFeedback(STATE.mode === 'task' ? 'TASK MODE' : 'NAV MODE');
            if(window.spatialAudio) window.spatialAudio.stopMicroTone();
            updateStatus('Scanning', 'active');
            startLoop();
        }
    }

    // Audio Feedback (Sonar / Micro)
    handleAudioFeedback(data);

    // Route to UI Handlers
    switch (data.type) {
        case 'result': updateNavUI(data); break;
        case 'micro_result': updateMicroUI(data); break;
        case 'task_update': updateTaskUI(data); break;
        case 'inquiry_result': updateInquiryUI(data); break;
        case 'speak': speak(data.text); break;
    }
}

function handleAudioFeedback(data) {
    if (!window.spatialAudio) return;

    // Micro Mode
    if (data.type === 'micro_result') {
        const { x, y, action } = data;
        window.spatialAudio.updateMicroTone(x, y);

        // Geiger
        const dist = Math.sqrt(x*x + y*y);
        const maxDist = 140;
        const proximity = 1 - (Math.min(dist, maxDist) / maxDist);
        const now = Date.now();
        if (now - STATE.lastGeiger > (250 - (proximity * 200))) {
            window.spatialAudio.playGeigerClick(x, y);
            STATE.lastGeiger = now;
        }

        if (action === 'push') {
            window.spatialAudio.stopMicroTone();
            window.spatialAudio.playSuccess();
            showFeedback('PUSH NOW');
        }
        return;
    }

    // Nav Mode
    if (data.distance > 0) {
        if (data.target_detected) {
            window.spatialAudio.playTargetLocked(data.direction, data.distance);
        } else {
            window.spatialAudio.playSonar(data.direction, data.distance, data.priority);
        }
    }
}

function speak(text) {
    if (!text || !window.speechSynthesis) return;
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
}

export function sendFrame(blob) {
    if (STATE.ws && STATE.ws.readyState === WebSocket.OPEN) {
        STATE.ws.send(blob);
    }
}

export function sendInquiryData(imageBlob, audioBase64) {
    if (!STATE.ws || STATE.ws.readyState !== WebSocket.OPEN) return;
    
    // imageBlob is actually a dataURL in this context (from canvas)
    STATE.ws.send(JSON.stringify({
        type: 'inquiry',
        image: imageBlob, 
        audio: audioBase64
    }));
}
