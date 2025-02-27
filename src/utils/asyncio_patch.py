import asyncio
import sys
import logging
import warnings

logger = logging.getLogger(__name__)

def patch_asyncio_windows():
    """
    Patch asyncio's ProactorEventLoop to handle Windows connection reset errors gracefully.
    This addresses the ConnectionResetError issue during application shutdown.
    """
    if sys.platform != 'win32':
        return  # Only apply on Windows
    
    logger.info("Applying Windows asyncio patch for connection reset errors")
    
    # Patch ProactorEventLoop.close
    _original_close = asyncio.proactor_events._ProactorBasePipeTransport.close
    
    def _patched_close(self, *args, **kwargs):
        try:
            _original_close(self, *args, **kwargs)
        except ConnectionResetError as e:
            # Suppress ConnectionResetError during close
            logger.debug(f"Suppressed asyncio connection reset: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error in patched asyncio close: {e}")
    
    asyncio.proactor_events._ProactorBasePipeTransport.close = _patched_close
    
    # Also patch the connection lost callback if needed
    _original_call_connection_lost = asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost
    
    def _patched_call_connection_lost(self, exc):
        try:
            _original_call_connection_lost(self, exc)
        except ConnectionResetError as e:
            # Suppress ConnectionResetError during connection lost handling
            logger.debug(f"Suppressed asyncio connection reset in _call_connection_lost: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error in patched _call_connection_lost: {e}")
    
    asyncio.proactor_events._ProactorBasePipeTransport._call_connection_lost = _patched_call_connection_lost

# Optionally silence ResourceWarning related to unclosed sockets
def silence_resource_warnings():
    """Silence ResourceWarning about unclosed sockets during shutdown."""
    warnings.filterwarnings("ignore", category=ResourceWarning, message="unclosed.*<socket.socket.*>")
