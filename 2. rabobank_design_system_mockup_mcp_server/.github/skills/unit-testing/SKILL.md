---
name: unit-testing
description: 'Design, implement, and validate unit tests for Python code. Use when adding features, fixing bugs, preventing regressions, or improving confidence before refactors. Keywords: pytest, test cases, mocks, assertions, edge cases, coverage, regression tests.'
argument-hint: 'What should be tested? (function/module/bug scenario)'
user-invocable: true
disable-model-invocation: false
---

# Unit Testing Workflow

## Outcome
Produce reliable unit tests that verify behavior, catch regressions, and document expected outcomes for normal, edge, and failure paths.

## When to Use
- New feature implementation needs test coverage.
- Bug fix requires a regression test.
- Refactor needs safety checks before and after changes.
- Existing behavior is unclear and should be specified with tests.

## Inputs
- Target under test: function, class, module, or bug scenario.
- Expected behavior: success cases, invalid input handling, and error behavior.
- Runtime/tooling context: test framework and command used in the repository.

## Procedure
1. Identify the test target and expected behavior.
2. Enumerate test cases before writing code:
- Happy path behavior.
- Boundary and edge conditions.
- Invalid input and error handling.
- Regression case for known bug reports.
3. Confirm test location and naming convention in the repository (for example, tests/ and test_*.py).
4. Write focused tests with clear Arrange/Act/Assert structure.
5. Isolate external dependencies with mocks/stubs/fixtures where needed.
6. Prefer deterministic data and avoid network/time randomness unless explicitly controlled.
7. Run the smallest relevant subset first, then run a broader suite.
8. Analyze failures by category:
- Test bug (assertion or setup issue).
- Product bug (code behavior mismatch).
- Environment/config issue.
9. Fix issues and rerun until tests are stable.
10. Validate quality gates before completion.

## Decision Points
- If behavior is ambiguous: derive expectations from docs/issues/acceptance criteria before asserting.
- If setup is heavy or flaky: mock boundaries and keep unit tests fast.
- If a fix changes behavior: update/add regression tests and document intent in test names.
- If running full suite is expensive: run targeted tests first, then full suite before finalizing.

## Quality Criteria
- Tests are deterministic and isolated.
- Assertions check behavior, not implementation details where avoidable.
- Edge/error paths are covered, not only happy paths.
- Regression tests exist for reproduced bugs.
- Test names describe behavior clearly.
- All touched tests pass locally.

## Completion Checklist
- Added or updated unit tests for every changed behavior.
- Added at least one negative/edge case where relevant.
- Executed targeted tests and at least one broader validation pass.
- Verified failures were resolved and not hidden with brittle assertions.
- Summarized what was tested and residual risk.

## Suggested Command Patterns (Python)
- Run all tests: `uv run pytest`
- Run one file: `uv run pytest tests/test_module.py`
- Run one test: `uv run pytest tests/test_module.py::test_case_name`
- Stop on first failure: `uv run pytest -x`
- Show verbose output: `uv run pytest -v`

## Example Prompts
- /unit-testing Add tests for get_account_balance covering valid and unknown account numbers.
- /unit-testing Create a regression test for a bug where empty input should return a user-friendly error.
- /unit-testing Improve coverage for main.py and prioritize edge cases.
- /unit-testing Review existing tests and suggest missing unit test scenarios.
