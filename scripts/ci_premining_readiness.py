"""SCHED-COMP-018R2: strictly pre-intervention restart classification.

This only authorizes a fresh boot after an RCON socket timeout in the
chunk-forceload command, if an independently written atomic stage record
proves no player mining packet was sent. No recovery or run replacement after
the event begins, after idle tick gate failure, or after any game-state error.
"""
from __future__ import annotations

from pathlib import Path
import json


PROTOCOL="SCHED-COMP-018R2"
FORCELOAD_STAGE="forceload_pending"
MAX_RETRIES_PER_ARM=1
MAX_RETRIES_PER_PHASE=2
SETUP_RCON_TIMEOUT_SECONDS=45
EVENT_OBSERVATION_CAP_SECONDS=150


def inspect_stage_file(path:Path)->dict:
    try:
        record=json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(record,dict):
            raise ValueError("stage JSON is not an object")
        return record
    except (OSError,ValueError) as error:
        return {"invalid_stage_record":str(error)}


def retryable_forceload_timeout(exit_code:int,stderr:str,stage:dict)->bool:
    if exit_code==0 or stage.get("protocol")!=PROTOCOL:
        return False
    if stage.get("stage")!=FORCELOAD_STAGE or stage.get("mining_started") is not False:
        return False
    history=stage.get("stage_history")
    if not isinstance(history,list) or not history:
        return False
    if history[-1].get("stage")!=FORCELOAD_STAGE:
        return False
    if any(event.get("mining_started") is not False for event in history):
        return False
    if not (
        "TimeoutError: timed out" in stderr
        and 'rcon.command(f"forceload add' in stderr
        and "run_veinminer_profile.py" in stderr
    ):
        return False
    return True


def allowed_retry(
    attempt_number:int,successful_or_failed_startups:int,
    exit_code:int,stderr:str,stage:dict
)->bool:
    return (
        attempt_number<=MAX_RETRIES_PER_ARM
        and successful_or_failed_startups<MAX_RETRIES_PER_PHASE
        and retryable_forceload_timeout(exit_code,stderr,stage)
    )
