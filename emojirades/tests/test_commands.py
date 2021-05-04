from emojirades.tests.helper import EmojiradeBotTester

import re


class TestBotCommands(EmojiradeBotTester):
    """
    Tests various game commands against the bot
    """

    def test_plusplus_new_game(self):
        """Cannot ++ someone when the game is not in progress"""
        state = self.workspace["gamestate"].state[self.config.channel]
        assert state["step"] == "new_game"

        self.send_event(self.events.plusplus)
        assert (
            self.config.channel,
            "Sorry, but we need to be guessing! Get the winner to start posting the next 'rade!",
        ) in self.responses

    def test_new_game_by_old_winner(self):
        """The old winner is allowed to 'reset' their rade if the game isn't in progress"""
        self.reset_and_transition_to("provided")
        state = self.workspace["gamestate"].state[self.config.channel]
        state["admins"].append(self.config.player_4)

        # Should be allowed
        self.send_event(self.events.new_game)
        assert state["step"] == "waiting"

        # Reset
        self.reset_and_transition_to("guessing")
        state = self.workspace["gamestate"].state[self.config.channel]
        state["admins"].append(self.config.player_4)

        # Should not be allowed
        self.send_event(self.events.new_game)
        assert state["step"] == "guessing"

    def test_leaderboard_output(self):
        """Ensure leaderboard output is consistent"""
        self.reset_and_transition_to("waiting")

        self.workspace["scorekeeper"].scoreboard[self.config.channel] = {
            "scores": {
                "David Pham": 168,
                "fendy Haman": 120,
                "Michael Mitchell": 118,
                "Timothy Sinclair": 100,
                "Stephen Verschuren": 81,
                "Mark Chaves": 81,
                "Andres Quillian": 81,
                "Justin Fendi": 24,
                "Scott Burke": 23,
                "Steve Robbins": 9,
                "Agung Alford": 9,
                "James Gream": 1,
            },
        }

        expected = """```
 :: All Time leaderboard ::

 1. David Pham         [ 168 points ]
 2. fendy Haman        [ 120 points ]
 3. Michael Mitchell   [ 118 points ]
 4. Timothy Sinclair   [ 100 points ]
 5. Stephen Verschuren [  81 points ]
 5. Mark Chaves        [  81 points ]
 5. Andres Quillian    [  81 points ]
 8. Justin Fendi       [  24 points ]
 9. Scott Burke        [  23 points ]
10. Steve Robbins      [   9 points ]
10. Agung Alford       [   9 points ]
12. James Gream        [   1 point  ]
```"""

        self.send_event(self.events.leaderboard)

        assert (self.config.channel, expected) in self.responses

    def test_fixwinner(self):
        """Ensure fixwinner does the right thing"""
        self.reset_and_transition_to("guessed")

        state = self.workspace["gamestate"].state[self.config.channel]

        self.send_event(self.events.fixwinner)
        assert state["old_winner"] == self.config.player_2
        assert state["winner"] == self.config.player_4
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_3
        ) == (0, 2)
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_4
        ) == (1, 1)

        # Check the user cannot award to themselves
        self.reset_and_transition_to("guessed")

        state = self.workspace["gamestate"].state[self.config.channel]

        override = {
            "text": f"<@{self.config.bot_id}> fixwinner <@{self.config.player_2}>"
        }
        self.send_event({**self.events.fixwinner, **override})

        expected = ":face_palm: You can't award yourself the win"
        assert (self.config.channel, expected) in self.responses

        assert state["old_winner"] == self.config.player_2
        assert state["winner"] == self.config.player_3
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_3
        ) == (1, 1)
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_4
        ) == (0, -1)

        # Check the user cannot award to the winner (no-op)
        self.reset_and_transition_to("guessed")

        state = self.workspace["gamestate"].state[self.config.channel]

        override = {
            "text": f"<@{self.config.bot_id}> fixwinner <@{self.config.player_3}>"
        }
        self.send_event({**self.events.fixwinner, **override})

        expected = "This won't actually do anything? :shrug::face_with_monocle:"
        assert (self.config.channel, expected) in self.responses

        assert state["old_winner"] == self.config.player_2
        assert state["winner"] == self.config.player_3
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_3
        ) == (1, 1)
        assert self.workspace["scorekeeper"].current_score(
            self.config.channel, self.config.player_4
        ) == (0, -1)

    def test_set_emojirade_banned_words(self):
        """Ensure that the emojirade can't contain banned words"""
        self.reset_and_transition_to("waiting")

        state = self.workspace["gamestate"].state[self.config.channel]

        banned_emojirade = dict(self.events.posted_emojirade)
        banned_emojirade["text"] = "emojirade foo :pie: bar"

        self.send_event(banned_emojirade)
        assert (
            self.config.bot_channel,
            "Sorry, but that emojirade contained a banned word/phrase :no_good:, try again?",
        ) in self.responses
        assert state["step"] == "waiting"

        banned_emojirade = dict(self.events.posted_emojirade)
        banned_emojirade["text"] = "emojirade foo :+1: bar"

        self.send_event(banned_emojirade)
        assert (
            self.config.bot_channel,
            "Sorry, but that emojirade contained a banned word/phrase :no_good:, try again?",
        ) in self.responses
        assert state["step"] == "waiting"

        self.send_event(self.events.posted_emojirade)
        assert state["step"] == "provided"

    def test_set_emojirade_raw_output(self):
        """Ensure that the emojirade passed to the winner isn't sanitized"""
        self.reset_and_transition_to("waiting")

        emojirade = "test-123-test_123"

        override = {"text": f"emojirade {emojirade}"}
        self.send_event({**self.events.posted_emojirade, **override})

        assert (
            self.config.player_2_channel,
            f"Hey, <@{self.config.player_1}> made the emojirade `{emojirade}`, good luck!",
        ) in self.responses

    def test_set_emojirade_alternatives_output(self):
        """Ensure that the emojirade alternatives output is expected"""
        self.reset_and_transition_to("waiting")

        emojirade = "foo | bar"

        override = {"text": f"emojirade {emojirade}"}
        self.send_event({**self.events.posted_emojirade, **override})

        assert (
            self.config.player_2_channel,
            f"Hey, <@{self.config.player_1}> made the emojirade `foo`, with alternatives `bar`, good luck!",
        ) in self.responses

    def test_set_emojirade_public_channel(self):
        """Ensure that the emojirade can only be set in a DM channel"""
        self.reset_and_transition_to("waiting")

        override = {"channel": self.config.channel}
        self.send_event({**self.events.posted_emojirade, **override})

        assert (
            self.config.player_1_channel,
            "Sorry, but this command can only be sent as a direct message!",
        ) in self.responses

    def test_redo_emojirade(self):
        """Ensure that a user can 'redo' an emojirade eg. typo"""
        self.reset_and_transition_to("provided")

        emojirade = "this_has_no typo"

        override = {"text": f"emojirade {emojirade}"}
        self.send_event({**self.events.posted_emojirade, **override})

        print(self.responses)

        assert (
            self.config.player_2_channel,
            f"Hey, <@{self.config.player_1}> made the emojirade `{emojirade}`, good luck!",
        ) in self.responses

    def test_user_override(self):
        self.reset_and_transition_to("guessing")

        state = self.workspace["gamestate"].state[self.config.channel]

        # Player 4 is not involved in this round
        override = {
            "user": self.config.player_4,
            "text": f"<@{self.config.player_3}>++ player=<@{self.config.player_2}>",
        }
        self.send_event({**self.events.manual_award, **override})

        assert state["step"] == "waiting"
        assert state["winner"] == self.config.player_3

    def test_channel_override(self):
        self.reset_and_transition_to("guessing")

        state = self.workspace["gamestate"].state[self.config.channel]

        override = {
            "channel": self.config.bot_channel,
            "text": f"{self.config.emojirade} channel=<#{self.config.channel}|emojirades>",
        }
        self.send_event({**self.events.correct_guess, **override})

        assert state["step"] == "waiting"
        assert state["winner"] == self.config.player_3

    def test_help(self):
        from emojirades.commands.registry import CommandRegistry

        self.send_event(self.events.help)

        commands = CommandRegistry.command_patterns()

        for command in commands.values():
            for example, description in command.examples:
                assert re.compile(
                    fr"{re.escape(example)}\s+{re.escape(description)}"
                ).search(self.responses[-2][1])

    def test_game_status(self):
        self.reset_and_transition_to("waiting")
        self.send_event(self.events.game_status)

        assert (
            self.config.channel,
            f"Status: Waiting for <@{self.config.player_1}> to provide a 'rade to {self.config.player_2}",
        ) in self.responses

        self.reset_and_transition_to("provided")
        self.send_event(self.events.game_status)

        assert (
            self.config.channel,
            f"Status: Waiting for <@{self.config.player_2}> to post an emoji to kick off the round!",
        ) in self.responses
