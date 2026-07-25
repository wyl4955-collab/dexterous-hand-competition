# Task execution status (published by task state machines)
string task_name         # e.g. "powder_weighing", "bean_picking"
string state             # current state: IDLE/RUNNING/SUCCESS/FAILED/TIMEOUT/ESTOP
float32 elapsed          # elapsed time in seconds
float32 score            # current score (if applicable)
string message           # human-readable status message
