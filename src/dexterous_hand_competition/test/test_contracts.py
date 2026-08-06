from dexterous_hand_competition.common.contracts import (
    ActionResult,
    ResultCode,
)


def test_action_result_factories():
    success = ActionResult.success('done', 1.2)
    assert success.ok
    assert success.code == ResultCode.OK
    assert success.elapsed_sec == 1.2

    failure = ActionResult.failure(ResultCode.TIMEOUT, 'late')
    assert not failure.ok
    assert failure.code == ResultCode.TIMEOUT


def test_dry_run_is_successful_but_explicit():
    result = ActionResult.dry_run('simulated')
    assert result.ok
    assert result.code == ResultCode.DRY_RUN

