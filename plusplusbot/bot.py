import os

import time

from plusplusbot.slack import SlackClient
from plusplusbot.scorekeeper import ScoreKeeper
from plusplusbot.gamestate import GameState

from plusplusbot.commands import Command

import logging

module_logger = logging.getLogger("PlusPlusBot.bot")


class PlusPlusBot(object):
    def __init__(self, scorefile, statefile):
        self.logger = logging.getLogger("PlusPlusBot.bot.Bot")

        self.scorekeeper = ScoreKeeper(scorefile)
        self.gamestate = GameState(statefile)

        slack_bot_token = os.environ.get("SLACK_BOT_TOKEN", None)

        if slack_bot_token is not None:
            self.slack = SlackClient(os.environ.get('SLACK_BOT_TOKEN'), self.logger)
        else:
            raise RuntimeError("Missing SLACK_BOT_TOKEN from environment vars")

        self.logger.debug("Initialised application instance")

    def match_event(self, event, commands):
        """
        If the event is valid and matches a command, perform the action the command details
        :param event:
        :return:
        """

        self.logger.debug("Handling event: {}".format(event))

        if "text" not in event:
            return None

        for pattern, (Command, description) in commands.items():
            if Command.match(event["text"], me=self.slack.bot_id):
                return Command(self.slack, event, scorekeeper=self.scorekeeper, gamestate=self.gamestate)

        return None

    def decode_channel(self, channel):
        """
        Figures out the channel destination
        """
        if channel.startswith("U"):
            # Channel is a User ID, which means the real channel is the IM with that user
            return self.slack.find_im(channel)
        else:
            raise NotImplementedError("Returned channel '{0}' wasn't decoded".format(channel))

    def listen_for_actions(self):
        commands = Command.prepare_commands()
        commands.update(Command.prepare_commands(self.scorekeeper.commands))
        commands.update(Command.prepare_commands(self.gamestate.commands))

        if not self.slack.ready:
            raise RuntimeError("is_ready has not been called/returned false")

        if not self.slack.sc.rtm_connect():
            raise RuntimeError("Failed to connect to the Slack API")

        self.logger.info("Slack is connected and listening for commands")

        while True:
            for event in self.slack.sc.rtm_read():
                if not event or "text" not in event or "channel" not in event:
                    self.logger.debug("Skipping event due to being invalid")
                    continue

                for GameCommand in self.gamestate.infer_commands(event):
                    action = GameCommand(self.slack, event, gamestate=self.gamestate)

                    for channel, response in action.execute():
                        if channel is not None:
                            channel = self.decode_channel(channel)
                        else:
                            channel = event["channel"]

                        self.slack.sc.rtm_send_message(channel, response)

                action = self.match_event(event, commands)

                if action:
                    self.logger.debug("Matched {0} for event {1}".format(action, event))
                    for channel, response in action.execute():
                        if channel is not None:
                            channel = self.decode_channel(channel)
                        else:
                            channel = event["channel"]

                        self.slack.sc.rtm_send_message(channel, response)
                else:
                    self.logger.debug("No match for event {0}".format(event))

            time.sleep(1)
