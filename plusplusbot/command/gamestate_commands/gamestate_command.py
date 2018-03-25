from plusplusbot.command.commands import Command


class GameStateCommand(Command):
    def __init__(self, *args, **kwargs):
        self.scorekeeper = kwargs.pop("scorekeeper")
        self.gamestate = kwargs.pop("gamestate")
        super().__init__(*args, **kwargs)
