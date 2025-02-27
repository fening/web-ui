import logging
from typing import Any, Dict, Optional, Type
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class ActionConverter:
    """
    Handles conversion between different action representations.
    Useful for translating between framework-specific action models.
    """
    
    def __init__(self):
        """Initialize the action converter with empty registry."""
        self.converters = {}
        
    def register_converter(self, 
                          source_action_type: str, 
                          target_action_type: str, 
                          converter_func: callable) -> None:
        """
        Register a conversion function between action types.
        
        Args:
            source_action_type: Source action type identifier
            target_action_type: Target action type identifier
            converter_func: Function that performs the conversion
        """
        key = (source_action_type, target_action_type)
        self.converters[key] = converter_func
        logger.debug(f"Registered action converter: {source_action_type} -> {target_action_type}")
    
    def convert_action(self, 
                      action: Any, 
                      target_action_type: str) -> Optional[Any]:
        """
        Convert an action from one type to another.
        
        Args:
            action: The source action object
            target_action_type: Target action type identifier
            
        Returns:
            Converted action, or None if conversion failed
        """
        if action is None:
            return None
            
        # Try to get action type from object
        if hasattr(action, 'action_type'):
            source_action_type = action.action_type
        else:
            # Try to infer from class name
            source_action_type = type(action).__name__
        
        converter = self.converters.get((source_action_type, target_action_type))
        
        if not converter:
            logger.warning(f"No converter registered for {source_action_type} -> {target_action_type}")
            return None
            
        try:
            return converter(action)
        except Exception as e:
            logger.error(f"Error converting action: {e}")
            return None
    
    def can_convert(self, source_action_type: str, target_action_type: str) -> bool:
        """
        Check if a converter exists for the given action types.
        
        Args:
            source_action_type: Source action type identifier
            target_action_type: Target action type identifier
            
        Returns:
            True if a converter exists, False otherwise
        """
        return (source_action_type, target_action_type) in self.converters
