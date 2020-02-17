from plusplusbot.command.gamestate_commands.gamestate_command import GameStateCommand
from plusplusbot.wrappers import only_guessing

import random


class CorrectGuess(GameStateCommand):
    description = "Manually award a player the win, when automated inferrence didn't work"
    short_description = "Manually award a player the win"

    patterns = (
        r"<@(?P<target_user>[0-9A-Z]+)>[\s]*\+\+",
    )
    example = "@winner ++"

    first_emojis = [
        ":tada:",
        ":first_place_medal:",
        ":sunglasses:",
        ":nerd_face:",
        ":birthday:",
        ":beers:",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def prepare_args(self, event):
        super().prepare_args(event)

    @only_guessing
    def execute(self):
        yield from super().execute()

        state = self.gamestate.state[self.args["channel"]]

        if self.args["target_user"] in (state["old_winner"], state["winner"]):
            yield (None, "You're not allowed to award current players the win >.>")
            return

        if self.args["user"] != state["winner"]:
            yield (None, "You're not the current winner, stop awarding other people the win >.>")
            return

        # Save a copy of the emojirade, as below clears it
        raw_emojirades = list(state["emojirade"])

        self.gamestate.correct_guess(self.args["channel"], self.args["target_user"])
        score, is_first = self.scorekeeper.plusplus(self.args["channel"], self.args["target_user"])

        if is_first:
            emoji = " {0}".format(random.choice(self.first_emojis))
        else:
            emoji = ""

        first_emojirade = raw_emojirades[0]

        if len(raw_emojirades) > 1:
            alternatives = ", with alternatives " + " OR ".join(["`{0}`".format(i) for i in raw_emojirades[1:]])
        else:
            alternatives = ""

        yield (None, "Congrats <@{0}>, you're now at {1} point{2}{3}".format(state["winner"], score, "s" if score > 1 else "", emoji))
        yield (None, "The correct emojirade was `{0}`{1}".format(first_emojirade, alternatives))

        yield (state["old_winner"], "You'll now need to send me the new 'rade for <@{0}>".format(state["winner"]))
        yield (state["old_winner"], "Please reply back in the format `emojirade Point Break` if `Point Break` was the new 'rade")
