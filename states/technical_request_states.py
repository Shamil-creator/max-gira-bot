from aiogram.fsm.state import StatesGroup,State

class Technical_States(StatesGroup):
    get_problem_state = State()
    wait_image_state = State()
