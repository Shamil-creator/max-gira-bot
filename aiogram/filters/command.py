class Command:
    def __init__(self, command: str):
        self.command = command.lstrip('/')


class CommandStart(Command):
    def __init__(self):
        super().__init__('start')
