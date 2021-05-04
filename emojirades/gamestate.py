import logging
import json
import re

from collections import defaultdict

from emojirades.commands.gamestate_commands.inferred_correct_guess_command import (
    InferredCorrectGuessCommand,
)
from emojirades.helpers import sanitize_text, match_emojirade, match_emoji
from emojirades.helpers import ScottFactorExceededException
from emojirades.handlers import get_configuration_handler

from emojirades.commands import BaseCommand
from emojirades.slack.event import Event

module_logger = logging.getLogger("EmojiradesBot.gamestate")


def get_handler(filename):
    class GameStateConfigHandler(get_configuration_handler(filename)):
        """
        Handles CRUD for the Game State configuration file
        """

        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

        def load(self):
            bytes_content = super().load()

            if bytes_content is None or not bytes_content:
                return None

            return json.loads(bytes_content.decode("utf-8"))

        def save(self, state):
            bytes_content = json.dumps(state).encode("utf-8")

            super().save(bytes_content)

    return GameStateConfigHandler(filename)


class GameState(object):
    """
    Game State Machine:
    Winner     1: Communicates emojirade with emojis
    Guessers   2: Anyone else who isn't the Winner/Old Winner
    Guessers   3: Attempt guesses at the emojirade
    Guesser    4: Wins by guessing the emojirade
    Winner     5: Is now the Old Winner
    Guesser    6: Is now the Winner
    Old Winner 7: Makes a new emojirade and sends it to the Winner
               8: Go to step 1

    Steps of the game:
        new_game  : The game has no previous winner, manual intervention required
        waiting   : The old winner has not provided the winner with the new emojirade
        provided  : The winner has not posted anything since having recieved the emojirade
        guessing  : The winner has posted since having recieved the emojirade

    Step transitions:
        set_winners   : new_game -> waiting
        set_emojirade : waiting  -> provided
        winner_posted : provided -> guessing
        correct_guess : guessing -> waiting

    Step Overview
        new_game -(set_winners)-> waiting -(set_emojirade)-> provided -(winner_posted)-> guessing -|
                                     ^-----------------------(correct_guess)-----------------------|
    """

    class InvalidStateException(Exception):
        pass

    def __init__(self, filename=None):
        self.logger = logging.getLogger("EmojiradesBot.gamestate.GameState")
        self.config = get_handler(filename)

        def state_factory():
            return {
                "step": "new_game",
                "old_winner": None,
                "winner": None,
                "emojirade": None,
                "raw_emojirade": None,
                "admins": [],
            }

        self.state = defaultdict(state_factory)

        if filename is not None:
            existing_state = self.config.load()

            if existing_state is not None:
                self.state.update(existing_state)
                self.logger.info(f"Loaded game state from {filename}")

    def in_progress(self, channel):
        return self.state[channel]["step"] not in ("new_game",)

    def not_in_progress(self, channel):
        return self.state[channel]["step"] in ("new_game", "waiting")

    def guessing(self, channel):
        return self.state[channel]["step"] in ("guessing",)

    def infer_commands(self, event: Event):
        """
        Keeps tabs on the conversation and updates gamestate if required
        Not to be called directly, used as another command source from the bot
        """
        channel = str(event.channel)
        user = str(event.player_id)
        text = str(event.text)
        state = self.state[channel]

        if self.is_admin(channel, user):
            # Double check if we're overriding the channel
            channel_override_match = BaseCommand.channel_override_regex.match(text)

            if channel_override_match:
                original_channel = channel
                channel = channel_override_match.groupdict()["channel_override"]

                text = text.replace(
                    channel_override_match.groupdict()["override_cmd"], ""
                )

            # Double check if we're overriding the user
            user_override_match = BaseCommand.user_override_regex.match(text)

            if user_override_match:
                original_user = user
                user = user_override_match.groupdict()["user_override"]

                text = text.replace(user_override_match.groupdict()["override_cmd"], "")

        # User the overridden channel if applicable
        state = self.state[channel]

        # Check to see if the winner is posting emoji's
        if (
            state["step"] == "provided"
            and user == state["winner"]
            and match_emoji(text)
        ):
            self.winner_posted(channel)

        # Check to see if the users guess is right!
        elif state["step"] == "guessing" and user not in (
            state["old_winner"],
            state["winner"],
        ):
            guess = sanitize_text(text)

            try:
                if match_emojirade(guess, state["emojirade"]):
                    self.logger.debug(
                        f"emojirades='{'|'.join(state['emojirade'])}' guess='{guess}' status='correct'"
                    )

                    yield InferredCorrectGuessCommand
                else:
                    self.logger.debug(
                        f"emojirades='{'|'.join(state['emojirade'])}' guess='{guess}' status='incorrect'"
                    )
            except ScottFactorExceededException as e:
                self.logger.debug(
                    f"emojirade='{'|'.join(state['emojirade'])}' guess='{guess}' status='scott factor exceeded'"
                )

            if state.get("first_guess", False):
                state["first_guess"] = False

    def set_admin(self, channel, admin):
        """Sets a new game admin!"""
        if admin in self.state[channel]["admins"]:
            return False

        self.state[channel]["admins"].append(admin)
        self.save()

        return True

    def remove_admin(self, channel, admin):
        """Removes the admin status of a user"""
        if admin not in self.state[channel]["admins"]:
            return False

        self.state[channel]["admins"].remove(admin)
        self.save()

        return True

    def is_admin(self, channel, user):
        admins = self.state[channel].get("admins", [])

        if not admins:
            # No admins set yet, so everyone is an admin!
            return True

        if user in admins:
            return True

        return False

    def new_game(self, channel, old_winner, winner):
        """Winners should be the unique Slack User IDs"""
        self.state[channel]["old_winner"] = old_winner
        self.state[channel]["winner"] = winner
        self.state[channel]["step"] = "waiting"
        self.state[channel]["emojirade"] = None
        self.state[channel]["raw_emojirade"] = None
        self.save()

    def set_emojirade(self, channel, emojirades):
        """New emojirade word(s), 'emojirade' is a list of accepted answers"""
        if self.state[channel]["step"] not in ("waiting", "provided"):
            raise self.InvalidStateException(
                f"Expecting {channel}'s state to be 'waiting|provided', it is actually {self.state[channel]['step']}"
            )

        self.state[channel]["emojirade"] = [sanitize_text(i) for i in emojirades]
        self.state[channel]["raw_emojirade"] = emojirades

        self.state[channel]["step"] = "provided"
        self.save()

    def winner_posted(self, channel):
        """Winner has posted something after receiving the emojirade"""
        if self.state[channel]["step"] != "provided":
            raise self.InvalidStateException(
                f"Expecting {channel}'s state to be 'provided', it is actually {self.state['step']}"
            )

        self.state[channel]["step"] = "guessing"
        self.state[channel]["first_guess"] = True
        self.save()

    def correct_guess(self, channel, winner):
        """Guesser has guessed the correct emojirade"""
        if self.state[channel]["step"] != "guessing":
            raise self.InvalidStateException(
                f"Expecting {channel}'s state to be 'guessing', it is actually {self.state[channel]['step']}"
            )

        self.state[channel]["old_winner"] = self.state[channel]["winner"]
        self.state[channel]["winner"] = winner
        self.state[channel]["step"] = "waiting"
        self.state[channel]["emojirade"] = None
        self.state[channel]["raw_emojirade"] = None
        self.save()

    def game_status(self, channel):
        """Returns the game state"""
        return self.state[channel]

    def fixwinner(self, channel, winner):
        """Updates the current winner with the newly provided winner and handles score updates"""
        loser = self.state[channel]["winner"]
        self.state[channel]["winner"] = winner
        self.save()

        return loser, winner

    def save(self):
        self.config.save(self.state)
