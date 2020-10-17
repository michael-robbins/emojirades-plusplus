import logging
import boto3
import time
import os
import traceback

from emojirades.handlers import get_workspace_directory_handler
from emojirades.commands.registry import CommandRegistry
from emojirades.slack.slack_client import SlackClient
from emojirades.scorekeeper import ScoreKeeper
from emojirades.commands import BaseCommand
from emojirades.gamestate import GameState
from emojirades.slack.event import Event


class EmojiradesBot(object):
    DEFAULT_WORKSPACE="_default"

    def __init__(self):
        self.logger = logging.getLogger("Emojirades.Bot")
        self.workspaces = {}
        self.onboarding_queue = None

    def configure_workspace(self, score_file, state_file, auth_file, workspace_id=None):
        if workspace_id is None:
            workspace_id = EmojiradesBot.DEFAULT_WORKSPACE

        self.workspaces[workspace_id] = {
            "scorekeeper": ScoreKeeper(score_file),
            "gamestate": GameState(state_file),
            "slack": SlackClient(auth_file, self.logger),
        }

    def configure_workspaces(self, workspaces_dir, onboarding_queue):
        handler = get_workspace_directory_handler(workspaces_dir)

        for workspace in handler.workspaces():
            self.configure_workspace(**workspace)

        self.onboarding_queue = onboarding_queue

    def match_event(self, event: Event, commands: dict) -> BaseCommand:
        """
        If the event is valid and matches a command, yield the instantiated command
        :param event: the event object
        :param commands: a list of known commands
        :return Command: The matched command to be executed
        """
        self.logger.debug(f"Handling event: {event.data}")

        for GameCommand in self.gamestate.infer_commands(event):
            yield GameCommand(event, self.slack, self.scorekeeper, self.gamestate)

        for Command in commands.values():
            if Command.match(event.text, me=self.slack.bot_id):
                yield Command(event, self.slack, self.scorekeeper, self.gamestate)

    def decode_channel(self, channel):
        """
        Figures out the channel destination
        """
        if channel.startswith("C"):
            # Plain old channel, just return it
            return channel
        elif channel.startswith("D"):
            # Direct message channel, just return it
            return channel
        elif channel.startswith("U"):
            # Channel is a User ID, which means the real channel is the DM with that user
            dm_id = self.slack.find_im(channel)

            if dm_id is None:
                raise RuntimeError(
                    f"Unable to find direct message channel for '{channel}'"
                )

            return dm_id
        else:
            raise NotImplementedError(f"Returned channel '{channel}' wasn't decoded")

    def handle_event(self, **payload):
        try:
            self._handle_event(**payload)
        except Exception as e:
            if logging.root.level == logging.DEBUG:
                traceback.print_exc()
            raise e

    def _handle_event(self, **payload):
        commands = CommandRegistry.command_patterns()

        event = Event(payload["data"], self.slack)
        webclient = payload["web_client"]
        self.slack.set_webclient(webclient)

        if not event.valid():
            self.logger.debug("Skipping event due to being invalid")
            return

        for command in self.match_event(event, commands):
            self.logger.debug(f"Matched {command} for event {event.data}")

            for channel, response in command.execute():
                self.logger.debug("------------------------")

                self.logger.debug(
                    f"Command {command} executed with response: {(channel, response)}"
                )
                if channel is not None:
                    channel = self.decode_channel(channel)
                else:
                    channel = self.decode_channel(event.channel)

                if isinstance(response, str):
                    # Plain strings are assumed as 'chat_postMessage'
                    webclient.chat_postMessage(channel=channel, text=response)
                    continue

                func = getattr(webclient, response["func"], None)

                if func is None:
                    raise RuntimeError(f"Unmapped function '{response['func']}'")

                args = response.get("args", [])
                kwargs = response.get("kwargs", {})

                if kwargs.get("channel") is None:
                    kwargs["channel"] = channel

                func(*args, **kwargs)

    def listen_for_commands(self):
        self.logger.info("Starting Slack monitor")
        self.slack.start()
