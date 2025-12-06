# Test Suite

This directory contains all test files for the interview service.

## Test Files

### Core Tests
- `test_interview_flow_core.py` - Core logic tests for phased interview flow (no external dependencies)
- `test_gemini_integration.py` - Gemini LLM integration tests (requires Gemini API key)
- `test_gateway.py` - API Gateway import and configuration tests

### Utility Scripts
- `check_gemini_keys.py` - Check if Gemini API keys are configured correctly

## Running Tests

### Core Logic Tests (No API keys required)
```bash
cd backend
python tests/test_interview_flow_core.py
```

### Gemini Integration Tests (Requires Gemini API key)
```bash
cd backend
python tests/test_gemini_integration.py
```

### Check API Keys
```bash
cd backend
python tests/check_gemini_keys.py
```

### API Gateway Tests
```bash
cd backend
python tests/test_gateway.py
```

## Test Results

Test results and documentation are stored in the `docs/` directory:
- `GEMINI_TEST_RESULTS.md` - Gemini integration test results
- `TEST_RESULTS_PHASED_FLOW.md` - Phased flow test results
- `INTERVIEW_FLOW_EXPLAINED.md` - Interview flow explanation

## Requirements

### For Core Tests
- No external dependencies (tests core logic only)

### For Gemini Integration Tests
- Gemini API key configured in `.env` file
- `google-generativeai` package installed
- `python-dotenv` package installed

## Notes

- All tests can be run from the `backend/` directory
- Test files automatically adjust their paths to import from the parent directory
- Gemini API key must be set in `.env` file in the `backend/` directory

