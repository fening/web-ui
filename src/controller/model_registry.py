import logging
from typing import Dict, Any, Type, Optional
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class CustomModelRegistry:
    """Registry for custom models used by the agent controller."""
    
    def __init__(self):
        """Initialize the model registry."""
        self.models: Dict[str, Type[BaseModel]] = {}
        self.converters = {}
        
    def register_model(self, name: str, model_class: Type[BaseModel]) -> None:
        """
        Register a new model with the registry.
        
        Args:
            name: Name to register the model under
            model_class: The Pydantic model class
        """
        if name in self.models:
            logger.warning(f"Overwriting existing model registration for '{name}'")
        
        self.models[name] = model_class
        logger.debug(f"Registered model '{name}'")
        
    def get_model(self, name: str) -> Optional[Type[BaseModel]]:
        """
        Get a model by name.
        
        Args:
            name: Name of the registered model
            
        Returns:
            The model class, or None if not found
        """
        return self.models.get(name)
    
    def register_converter(self, source_type: str, target_type: str, converter_func: callable) -> None:
        """
        Register a converter function between model types.
        
        Args:
            source_type: Source model type name
            target_type: Target model type name
            converter_func: Function that converts from source to target
        """
        key = (source_type, target_type)
        self.converters[key] = converter_func
        logger.debug(f"Registered converter from '{source_type}' to '{target_type}'")
    
    def get_converter(self, source_type: str, target_type: str) -> Optional[callable]:
        """
        Get a converter function for the specified types.
        
        Args:
            source_type: Source model type name
            target_type: Target model type name
            
        Returns:
            The converter function, or None if not found
        """
        return self.converters.get((source_type, target_type))
    
    def convert(self, source_instance: Any, target_type: str) -> Optional[Any]:
        """
        Convert an instance from one model type to another.
        
        Args:
            source_instance: Source instance to convert
            target_type: Target model type name
            
        Returns:
            Converted instance, or None if conversion failed
        """
        if source_instance is None:
            return None
        
        source_type = type(source_instance).__name__
        converter = self.get_converter(source_type, target_type)
        
        if converter:
            try:
                return converter(source_instance)
            except Exception as e:
                logger.error(f"Error during model conversion: {e}")
                return None
        else:
            logger.warning(f"No converter registered for '{source_type}' to '{target_type}'")
            return None
    
    def list_models(self) -> Dict[str, str]:
        """
        List all registered models.
        
        Returns:
            Dictionary of model names and their descriptions
        """
        return {name: model_cls.__doc__ or "No description" 
                for name, model_cls in self.models.items()}
