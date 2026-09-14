from typing import List, Dict, Optional
import time

class ComplianceEngine:
    def __init__(self, sop: List[Dict[str, str]]):
        """
        Initializes the Compliance Engine.
        :param sop: A list of dictionaries defining the Standard Operating Procedure.
                    Example: [{"id": "step1", "description": "Unpack the box"}]
        """
        self.sop = sop
        self.state = []
        for step in self.sop:
            self.state.append({
                "id": step["id"],
                "description": step["description"],
                "status": "Pending", # Pending, In Progress, Completed, Missed
                "timestamp_start": None,
                "timestamp_end": None
            })
        
        self.current_step_index = 0

    def update(self, detected_action_desc: str, current_time: float) -> List[Dict]:
        """
        Updates the state machine based on the detected action.
        :param detected_action_desc: The description of the action detected by the AI.
        :param current_time: The current timestamp in the video.
        """
        if detected_action_desc == "None" or detected_action_desc == "Error":
            return self.state
            
        # Find which step matches the detected action
        detected_index = -1
        for i, step in enumerate(self.state):
            if step["description"].lower() == detected_action_desc.lower():
                detected_index = i
                break
                
        if detected_index == -1:
             # Action detected is not part of the SOP, ignore for now
             return self.state
             
        # If we detected a step that is further ahead than our expected current step,
        # we mark intermediate steps as 'Missed'
        if detected_index > self.current_step_index:
            for i in range(self.current_step_index, detected_index):
                if self.state[i]["status"] == "Pending":
                     self.state[i]["status"] = "Missed"
            self.current_step_index = detected_index
            
        # Update the currently detected step
        if self.state[detected_index]["status"] == "Pending":
            self.state[detected_index]["status"] = "In Progress"
            self.state[detected_index]["timestamp_start"] = current_time
            
        # Simple heuristic: If we are in progress, but we suddenly detect a new step,
        # we consider the previous "In Progress" step as "Completed".
        # This requires more complex logic for overlapping actions.
        # For MVP, we will assume actions are strictly sequential.
        if detected_index == self.current_step_index and self.state[detected_index]["status"] == "In Progress":
             # We might need a mechanism to explicitly close a step. 
             # Let's say if we detect the SAME action again, it means it's still ongoing.
             pass
             
        # Optional: A mechanism to mark a step as 'Completed'. 
        # For simplicity, if we move to step N+1, step N is marked Completed.
        if detected_index > 0 and self.state[detected_index-1]["status"] == "In Progress":
             self.state[detected_index-1]["status"] = "Completed"
             self.state[detected_index-1]["timestamp_end"] = current_time

        return self.state

    def get_expected_actions(self) -> List[str]:
        """Returns a list of all action descriptions for the NIM to look out for."""
        return [step["description"] for step in self.sop]
