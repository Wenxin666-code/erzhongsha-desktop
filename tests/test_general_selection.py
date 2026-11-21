import random
import unittest

from main import (
    GAMEPLAY_SEAT_IS_AI, GENERAL_SELECTION_SEAT_IS_AI,
)
from src.general_selection import (
    MAX_GENERAL_CANDIDATES, GeneralSelectionState,
)
from src.models import General


def general(index, *, playable=True):
    return General(
        id=f"general-{index}",
        name=f"武将{index}",
        kingdom="魏",
        hp=4,
        skills=[],
        playable=playable,
    )


class GeneralSelectionTest(unittest.TestCase):
    def test_local_player_selects_both_seats_but_second_is_ai_in_game(self):
        state = GeneralSelectionState.create(
            [general(0), general(1)],
            GENERAL_SELECTION_SEAT_IS_AI,
            random.Random(1),
        )

        self.assertFalse(state.current_is_ai)
        self.assertTrue(state.choose(0, state.candidates[0]))
        self.assertFalse(state.current_is_ai)
        self.assertTrue(state.choose(1, state.candidates[1]))
        self.assertTrue(state.complete)
        self.assertEqual(GAMEPLAY_SEAT_IS_AI, (False, True))

    def test_candidate_pool_only_uses_up_to_eight_playable_generals(self):
        generals = [
            *(general(index) for index in range(10)),
            general(10, playable=False),
        ]

        state = GeneralSelectionState.create(
            generals,
            (False, True),
            random.Random(7),
        )

        self.assertEqual(
            len(state.candidates), MAX_GENERAL_CANDIDATES
        )
        self.assertTrue(
            all(candidate.playable for candidate in state.candidates)
        )
        self.assertTrue(
            all(
                candidate.default_skin_id == "default"
                for candidate in state.candidates
            )
        )
        self.assertNotIn("general-10", {
            candidate.id for candidate in state.candidates
        })

    def test_seats_choose_in_order_and_cannot_reuse_general(self):
        first, second = general(0), general(1)
        state = GeneralSelectionState.create(
            [first, second],
            (False, True),
            random.Random(2),
        )
        first_choice = state.candidates[0]
        second_choice = state.candidates[1]

        self.assertFalse(state.choose(1, first_choice))
        self.assertTrue(state.choose(0, first_choice))
        self.assertTrue(state.is_selected(first_choice))
        self.assertFalse(state.choose(1, first_choice))
        self.assertTrue(state.choose(1, second_choice))
        self.assertTrue(state.complete)
        self.assertEqual(
            state.ordered_selections(),
            (first_choice, second_choice),
        )

    def test_ai_randomly_chooses_from_remaining_generals(self):
        state = GeneralSelectionState.create(
            [general(index) for index in range(4)],
            (False, True),
            random.Random(3),
        )
        human_choice = state.candidates[0]
        self.assertTrue(state.choose(0, human_choice))

        ai_choice = state.choose_current_ai(random.Random(5))

        self.assertIn(ai_choice, state.candidates)
        self.assertIsNot(ai_choice, human_choice)
        self.assertTrue(state.complete)

    def test_selection_requires_enough_playable_generals(self):
        with self.assertRaisesRegex(
            ValueError, "可用武将数量少于"
        ):
            GeneralSelectionState.create(
                [general(0)],
                (False, True),
            )


if __name__ == "__main__":
    unittest.main()
