"""
NETRA WebSocket Routes
======================
Handles real-time communication with the client.
Manages the session lifecycle, frame reception, and error recovery.
"""

import json
import asyncio
import logging
from typing import Dict, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..models import SessionState
from ..utils import Console
from ..services.processor import (
    process_frame,
    process_micro_frame,
    process_task_frame,
    process_inquiry,
    safe_send_json,
    global_task_state
)

router = APIRouter()

@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Main WebSocket endpoint.
    Orchestrates the continuous frame processing loop.
    """
    await websocket.accept()
    
    # Initialize Session State
    state = SessionState()
    
    # Startup Logs
    Console.header()
    Console.log('connect', 'Client connected', 'green')

    # RESTORE STATE: If client is reconnecting, try to restore task
    if global_task_state.is_valid():
        state.task_state = global_task_state.to_task_state()
        state.mode = "task"
        Console.log('info', f"Restored Task: {global_task_state.task_name}", 'cyan')
        
        await safe_send_json(websocket, {
            "type": "task_update",
            "plan": state.task_state.plan,
            "current_step_index": state.task_state.current_step_index,
            "restored": True
        })
        
        # Announce resumption
        if state.task_state.current_step:
            await safe_send_json(websocket, {
                "type": "speak",
                "text": f"Resuming. Step: {state.task_state.current_step['instruction']}"
            })

    # CONCURRENCY:
    # We use an asyncio Event to trigger processing only when a frame is ready.
    # This prevents tight loops and manages backpressure.
    frame_event = asyncio.Event()

    async def _frame_processor_loop():
        """
        Consumer task: Waits for frames and processes them.
        Run in parallel to the receive loop.
        """
        while True:
            try:
                # Wait for signal
                await frame_event.wait()
                frame_event.clear()
                
                # Check for item to process
                if state.latest_frame and not state.is_processing:
                    state.is_processing = True
                    frame_data = state.latest_frame
                    state.latest_frame = None  # Consume frame
                    
                    try:
                        # Route based on Mode
                        if state.mode == 'micro':
                            await process_micro_frame(frame_data, state, websocket)
                        elif state.mode == 'task':
                            await process_task_frame(frame_data, state, websocket)
                        else:
                            await process_frame(frame_data, state, websocket)
                            
                    except Exception as e:
                        logging.error(f"Frame Processing Exception: {e}")
                    finally:
                        state.is_processing = False
                        # If a new frame arrived *during* processing, trigger immediately
                        if state.latest_frame:
                            frame_event.set()
                            
            except asyncio.CancelledError:
                break
            except Exception as e:
                logging.error(f"Frame Loop Fatal Error: {e}")
                # Don't break main loop, just reset
                state.is_processing = False

    # Start the processor in background
    processor_task = asyncio.create_task(_frame_processor_loop())

    try:
        # PRODUCER LOOP: Reads messages from client
        while True:
            message = await websocket.receive()
            
            if message["type"] == "websocket.disconnect":
                break
            
            if "text" in message:
                # Handle control messages / inquiries
                try:
                    data = json.loads(message["text"])
                    if data.get("type") == "inquiry":
                        await process_inquiry(data, state, websocket)
                        # Sync state if inquiry started a task
                        if state.task_state.is_active:
                            global_task_state.update_from(state.task_state)
                except json.JSONDecodeError:
                    pass

            elif "bytes" in message:
                # Handle Video Frame
                state.frames_received += 1
                
                frame_payload = {
                    "image": message["bytes"], 
                    "heading": 0, 
                    "task": "navigation"
                }
                
                # HEAD-OF-LINE BLOCKING STRATEGY:
                # If we are already processing, DROP this frame (latest_frame overwritten).
                # Only set event if we weren't busy, or to update the "latest" pointer.
                if not state.is_processing:
                    state.latest_frame = frame_payload
                    frame_event.set()
                else:
                    # Still update the latest frame so when processor finishes, 
                    # it grabs the NEWEST one, not the old one.
                    state.latest_frame = frame_payload
                    state.frames_skipped += 1
                    # Note: We don't set frame_event here because the processor 
                    # checks for 'latest_frame' at the end of its cycle.

    except WebSocketDisconnect:
        Console.log('disconnect', 'Client disconnected', 'yellow')
    except Exception as e:
        logging.error(f"WebSocket Connection Error: {e}")
    finally:
        # CLEANUP
        # Save state one last time
        if state.task_state.is_active:
            global_task_state.update_from(state.task_state)
            Console.log('info', "Task state saved for reconnect", 'cyan')
            
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            pass
