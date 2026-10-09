"""Small checks for the failure modes that can cause wrong actions or lost work."""

import json
import tempfile
import unittest
from pathlib import Path

from arc.contracts import GestureDefinition, Prediction
from arc.gate import ActivationGate
from arc.profile import Profile, load_profile, save_profile
from arc.workshop import STEPS, Workshop


class ActivationTests(unittest.TestCase):
    def test_held_pose_fires_once_until_released(self):
        gate = ActivationGate()
        known = Prediction(gesture_id="next", reason="recognized")
        unknown = Prediction(reason="no hand")
        self.assertIsNone(gate.update(known, 0.0))
        self.assertEqual(gate.update(known, 0.7), "next")
        self.assertIsNone(gate.update(known, 2.0))
        self.assertIsNone(gate.update(unknown, 2.1))
        self.assertIsNone(gate.update(unknown, 2.5))
        self.assertIsNone(gate.update(known, 2.6))
        self.assertEqual(gate.update(known, 3.3), "next")

    def test_unstable_or_early_pose_does_not_fire(self):
        gate = ActivationGate(hold_seconds=0.1, release_seconds=0.1,
                              cooldown_seconds=1.0)
        a = Prediction(gesture_id="a")
        b = Prediction(gesture_id="b")
        unknown = Prediction()
        self.assertIsNone(gate.update(a, 0.0))
        self.assertIsNone(gate.update(b, 0.05))
        self.assertIsNone(gate.update(unknown, 0.1))
        self.assertIsNone(gate.update(a, 0.11))
        self.assertEqual(gate.update(a, 0.22), "a")
        gate.update(unknown, 0.3)
        gate.update(unknown, 0.41)
        self.assertIsNone(gate.update(a, 0.42))
        self.assertIsNone(gate.update(a, 0.7))  # cooldown still active
        self.assertEqual(gate.update(a, 1.23), "a")


class ProfileTests(unittest.TestCase):
    def test_gesture_mapping_and_progress_survive_restart(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            gesture = GestureDefinition("id-1", "Open palm", "next_step", [[0.0] * 63])
            original = Profile([gesture], 3, [0, 1, 2])
            save_profile(path, original)
            loaded = load_profile(path)
            self.assertEqual(loaded, original)
            self.assertEqual(json.loads(path.read_text())["version"], 1)

    def test_corrupt_feature_vector_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "profile.json"
            path.write_text(json.dumps({"version": 1, "gestures": [{
                "gesture_id": "id-1", "name": "Bad", "action": "next_step",
                "samples": [[0.0] * 62],
            }]}))
            with self.assertRaises(ValueError):
                load_profile(path)


class WorkshopTests(unittest.TestCase):
    def test_all_five_steps_and_boundaries(self):
        workshop = Workshop()
        workshop.apply("previous_step")
        self.assertEqual(workshop.index, 0)
        for index in range(len(STEPS)):
            self.assertEqual(workshop.index, index)
            self.assertEqual(workshop.apply("replay_step"), STEPS[index][1])
            workshop.apply("complete_step")
            workshop.apply("next_step")
        self.assertEqual(workshop.index, len(STEPS) - 1)
        self.assertEqual(len(workshop.completed), len(STEPS))


if __name__ == "__main__":
    unittest.main()
