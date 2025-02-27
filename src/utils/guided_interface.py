from __future__ import annotations  # Add this at the top of the file
import logging
import asyncio
from typing import Dict, List, Any, Optional, Callable, Union
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

class StepStatus(Enum):
    """Status of a single guided step"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress" 
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"

class GuidedStep:
    """Represents a single step in a guided process"""
    
    def __init__(
        self,
        title: str,
        description: str,
        step_id: str = None,
        detailed_instructions: str = None,
        requires_confirmation: bool = False,
        estimated_time: int = None  # in seconds
    ):
        self.id = step_id or str(uuid.uuid4())
        self.title = title
        self.description = description
        self.detailed_instructions = detailed_instructions
        self.requires_confirmation = requires_confirmation
        self.status = StepStatus.PENDING
        self.error_message = None
        self.estimated_time = estimated_time
        self.started_at = None
        self.completed_at = None
        self.user_notes = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "detailed_instructions": self.detailed_instructions,
            "requires_confirmation": self.requires_confirmation,
            "status": self.status.value,
            "error_message": self.error_message,
            "estimated_time": self.estimated_time,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "user_notes": self.user_notes
        }

class GuidedProcess:
    """A step-by-step guided process"""
    
    def __init__(
        self, 
        name: str,
        description: str,
        process_id: str = None,
        auto_advance: bool = False
    ):
        self.id = process_id or str(uuid.uuid4())
        self.name = name
        self.description = description
        self.steps: List[GuidedStep] = []
        self.current_step_index = -1
        self.auto_advance = auto_advance
        self.on_step_change_callbacks: List[Callable[[GuidedStep], None]] = []
        self.on_complete_callbacks: List[Callable[["GuidedProcess"], None]] = []
        
    def add_step(self, step: GuidedStep) -> GuidedStep:
        """Add a step to the process"""
        self.steps.append(step)
        return step
        
    def get_current_step(self) -> Optional[GuidedStep]:
        """Get the current step"""
        if 0 <= self.current_step_index < len(self.steps):
            return self.steps[self.current_step_index]
        return None
    
    def start(self):
        """Start the guided process"""
        if self.steps and self.current_step_index == -1:
            self.advance_to_next_step()
            return True
        return False
    
    def advance_to_next_step(self) -> Optional[GuidedStep]:
        """Advance to the next step"""
        # Complete current step if it exists
        current = self.get_current_step()
        if current and current.status == StepStatus.IN_PROGRESS:
            current.status = StepStatus.COMPLETED
            from datetime import datetime
            current.completed_at = datetime.now().isoformat()
            
        # Move to next step
        if self.current_step_index + 1 < len(self.steps):
            self.current_step_index += 1
            next_step = self.steps[self.current_step_index]
            next_step.status = StepStatus.IN_PROGRESS
            from datetime import datetime
            next_step.started_at = datetime.now().isoformat()
            
            # Notify step change
            for callback in self.on_step_change_callbacks:
                try:
                    callback(next_step)
                except Exception as e:
                    logger.error(f"Error in step change callback: {e}")
                    
            return next_step
        else:
            # Process is complete
            for callback in self.on_complete_callbacks:
                try:
                    callback(self)
                except Exception as e:
                    logger.error(f"Error in process complete callback: {e}")
                    
            return None
    
    def mark_current_step_failed(self, error_message: str = None):
        """Mark the current step as failed"""
        current = self.get_current_step()
        if current:
            current.status = StepStatus.FAILED
            current.error_message = error_message
            from datetime import datetime
            current.completed_at = datetime.now().isoformat()
            
            # Notify step change
            for callback in self.on_step_change_callbacks:
                try:
                    callback(current)
                except Exception as e:
                    logger.error(f"Error in step change callback: {e}")
    
    def skip_current_step(self):
        """Skip the current step"""
        current = self.get_current_step()
        if current:
            current.status = StepStatus.SKIPPED
            from datetime import datetime
            current.completed_at = datetime.now().isoformat()
            
            return self.advance_to_next_step()
        return None
    
    def get_progress(self) -> Dict[str, Any]:
        """Get current progress information"""
        total_steps = len(self.steps)
        if total_steps == 0:
            return {"progress": 0, "completed": 0, "total": 0}
            
        completed = sum(1 for step in self.steps 
                      if step.status in [StepStatus.COMPLETED, StepStatus.SKIPPED])
        
        return {
            "progress": completed / total_steps,
            "completed": completed,
            "total": total_steps,
            "current_step": self.current_step_index + 1 if self.current_step_index >= 0 else 0
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation"""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": [step.to_dict() for step in self.steps],
            "current_step_index": self.current_step_index,
            "progress": self.get_progress()
        }
    
    def on_step_change(self, callback: Callable[[GuidedStep], None]):
        """Register a callback for step changes"""
        if callback not in self.on_step_change_callbacks:
            self.on_step_change_callbacks.append(callback)
    
    def on_complete(self, callback: Callable[["GuidedProcess"], None]):
        """Register a callback for process completion"""
        if callback not in self.on_complete_callbacks:
            self.on_complete_callbacks.append(callback)

class GuidedProcessManager:
    """Manages guided processes"""
    
    def __init__(self):
        self.processes: Dict[str, GuidedProcess] = {}
        self.active_process_id: Optional[str] = None
        
    def create_process(self, name: str, description: str, auto_advance: bool = False) -> GuidedProcess:
        """Create a new guided process"""
        process = GuidedProcess(name, description, auto_advance=auto_advance)
        self.processes[process.id] = process
        return process
    
    def get_process(self, process_id: str) -> Optional[GuidedProcess]:
        """Get a process by ID"""
        return self.processes.get(process_id)
    
    def get_active_process(self) -> Optional[GuidedProcess]:
        """Get the currently active process"""
        if self.active_process_id:
            return self.get_process(self.active_process_id)
        return None
    
    def set_active_process(self, process_id: str) -> bool:
        """Set the active process"""
        if process_id in self.processes:
            self.active_process_id = process_id
            return True
        return False
    
    def start_process(self, process_id: str) -> bool:
        """Start a specific process"""
        process = self.get_process(process_id)
        if process:
            if process.start():
                self.active_process_id = process_id
                return True
        return False
    
    def advance_active_process(self) -> Optional[GuidedStep]:
        """Advance the active process to the next step"""
        process = self.get_active_process()
        if process:
            return process.advance_to_next_step()
        return None

# Global manager instance
guided_process_manager = GuidedProcessManager()
