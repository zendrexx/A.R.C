"""Five-step hands-free assembly tutorial and its local actions."""

from dataclasses import dataclass, field

STEPS = (
    ("Prepare the parts", "Place the base, upright arm, pin, and thumb screw on a clear table."),
    ("Align the arm", "Set the upright arm into the slot on the base. Keep its holes aligned."),
    ("Insert the pin", "Slide the pin through the aligned holes to hold the arm in place."),
    ("Secure the stand", "Tighten the thumb screw until the arm stays upright without wobbling."),
    ("Check the result", "Set a light object on the stand and verify it remains stable."),
)


@dataclass
class Workshop:
    index: int = 0
    completed: set[int] = field(default_factory=set)

    def apply(self, action: str) -> str:
        if action == "next_step":
            self.index = min(self.index + 1, len(STEPS) - 1)
            return "Moved to the next step"
        if action == "previous_step":
            self.index = max(self.index - 1, 0)
            return "Moved to the previous step"
        if action == "complete_step":
            self.completed.add(self.index)
            return "Step marked complete"
        if action == "replay_step":
            return STEPS[self.index][1]
        raise ValueError(f"Unknown action: {action}")

