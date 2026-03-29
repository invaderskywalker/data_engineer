PROJECT_STATUS_VALUE_TO_CODE = {
    "on_track": 1,
    "at_risk": 2,
    "compromised": 3,
}

CODE_TO_PROJECT_STATUS_VALUE = {value: key for key, value in PROJECT_STATUS_VALUE_TO_CODE.items()}


PROJECT_STATUS_TYPE_TO_CODE = {
    "scope": 1,
    "schedule": 2,
    "spend": 3,
}

CODE_TO_PROJECT_STATUS_TYPE = {value: key for key, value in PROJECT_STATUS_TYPE_TO_CODE.items()}
