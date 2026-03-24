from aiogram.fsm.state import StatesGroup,State

class NotificationsStates(StatesGroup):
    Notify_Menu_State = State()
    Notify_of_termination_State = State()
    Agreement_termination_of_the_contract_State = State()
    Coordination_of_repair_work_State = State()
    Wait_message_of_repair_work_State = State()
    Wait_document_for_termination_State = State()