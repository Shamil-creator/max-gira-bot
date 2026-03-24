from aiogram.fsm.state import StatesGroup, State

class Repair_State(StatesGroup):
    Wait_document_for_termination_State = State()