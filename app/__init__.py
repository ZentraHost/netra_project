"""
NETRA - Visual Navigation Assistant
Application Factory Module

This module defines the `create_app` factory function, which initializes
the FastAPI application, mounts static resources, and registers routers.
"""

import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from .config import STATIC_DIR, TEMPLATES_DIR
from .routes import pages, websocket
from .utils import Console


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan events for the FastAPI application.
    Handles startup and shutdown logic.
    """
    # Startup: Print header and log initialization
    Console.header()
    logging.info("NETRA Application initialized successfully.")
    
    yield
    
    # Shutdown: Clean up resources if needed
    logging.info("NETRA Application shutting down...")


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Returns:
        FastAPI: The configured application instance.
    """
    # Create FastAPI app with metadata and lifespan
    app = FastAPI(
        title="NETRA",
        description="Advanced Visual Navigation Assistant",
        version="1.0.0",
        lifespan=lifespan
    )
    
    # Mount static files
    if STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
    else:
        logging.warning(f"Static directory not found at {STATIC_DIR}")
    
    # Include routers
    app.include_router(pages.router)
    app.include_router(websocket.router)
    
    return app


# Global templates instance for use in routes
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
