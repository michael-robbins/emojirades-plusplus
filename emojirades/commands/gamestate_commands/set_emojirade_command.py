from emojirades.wrappers import only_in_progress, only_as_direct_message
from emojirades.checks import emojirade_is_banned
from emojirades.commands import BaseCommand


class SetEmojiradeCommand(BaseCommand):
    description = "Sets the new emojirade to be guessed"

    patterns = (r"^emojirade[s]* (?P<emojirade>.+)",)

    examples = [
        ("emojirade foo", "Sets the new emojirade to 'foo'"),
        (
            "emojirade foo | bar",
            "Sets the new emojirade to 'foo' with 'bar' alternative",
        ),
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def prepare_args(self, event):
        super().prepare_args(event)

        # No matter what the final channel is, save the original one
        # This will override the 'original_channel' from an admin override
        # /shrug
        self.args["original_channel"] = self.args["channel"]

        # Figure out the channel to use
        for channel_name, channel in self.gamestate.state.items():
            if (
                channel["step"] == "waiting"
                and channel["old_winner"] == self.args["user"]
            ):
                # First channel that is 'waiting for a rade'
                self.args["channel"] = channel_name
                break
            elif (
                channel["step"] == "provided"
                and channel["old_winner"] == self.args["user"]
            ):
                # User is 'redoing the rade'
                self.args["channel"] = channel_name
                break
        else:
            self.args["channel"] = None

    @only_as_direct_message
    @only_in_progress
    def execute(self):
        yield from super().execute()

        if (
            self.args["user"]
            != self.gamestate.state[self.args["channel"]]["old_winner"]
        ):
            yield (
                None,
                f"Err <@{self.args['user']}> it's not your turn to provide the new 'rade :sweat:",
            )
            return

        if self.args["channel"] is None:
            yield (None, "There is no current game waiting for a new emojirade!")
            return

        if emojirade_is_banned(self.args["emojirade"]):
            yield (
                None,
                "Sorry, but that emojirade contained a banned word/phrase :no_good:, try again?",
            )
            return

        # Break the alternatives out
        raw_emojirades = [i.strip() for i in self.args["emojirade"].split("|")]

        self.gamestate.set_emojirade(self.args["channel"], raw_emojirades)

        winner = self.gamestate.state[self.args["channel"]]["winner"]

        # DM the winner with the new emojirade
        if len(raw_emojirades) > 1:
            alternatives = ", with alternatives " + " OR ".join(
                [f"`{i}`" for i in raw_emojirades[1:]]
            )
        else:
            alternatives = ""

        yield (
            winner,
            f"Hey, <@{self.args['user']}> made the emojirade `{raw_emojirades[0]}`{alternatives}, good luck!",
        )

        # Let the user know their 'rade has been accepted
        yield (
            self.args["user"],
            {
                "func": "reactions_add",
                "kwargs": {
                    "name": "+1",
                    "timestamp": self.args["ts"],
                },
            },
        )

        # Let everyone else know
        yield (self.args["channel"], f":mailbox: 'rade sent to <@{winner}>")
