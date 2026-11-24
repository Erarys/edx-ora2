"""Tests for the OpenAI Responses API client used by AI Assessment."""

import json
from unittest.mock import patch

from django.test import SimpleTestCase, override_settings

from openassessment.assessment.ai_client import (
    build_output_schema,
    essay_text_from_submission,
    get_ai_grading_config,
    grade_essay,
)
from openassessment.assessment.errors.ai import (
    AIGradingConfigurationError,
    AIGradingServiceError,
)


RUBRIC = {
    "prompts": [{"description": "Explain why testing matters."}],
    "criteria": [
        {
            "name": "accuracy",
            "label": "Accuracy",
            "prompt": "Is the answer accurate?",
            "options": [
                {"name": "poor", "label": "Poor", "points": 0, "explanation": "Incorrect"},
                {"name": "good", "label": "Good", "points": 2, "explanation": "Correct"},
            ],
        },
        {
            "name": "comments",
            "label": "Comments",
            "prompt": "Give written feedback.",
            "options": [],
        },
    ],
}


class FakeResponse:
    """Small context-manager response used to avoid network calls."""

    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return json.dumps(self.body).encode("utf-8")


class AIClientTest(SimpleTestCase):
    """Verify configuration, schema generation, and response parsing."""

    def test_schema_constrains_options_and_supports_feedback_only_criteria(self):
        schema = build_output_schema(RUBRIC)
        criteria = schema["properties"]["criteria"]["properties"]

        self.assertEqual(criteria["accuracy"]["properties"]["selected_option"]["enum"], ["poor", "good"])
        self.assertNotIn("selected_option", criteria["comments"]["properties"])
        self.assertFalse(schema["additionalProperties"])

    def test_extracts_multi_part_text_submission(self):
        submission = {"answer": {"parts": [{"text": "First"}, {"text": "Second"}, {"file": {}}]}}

        self.assertEqual(essay_text_from_submission(submission), "First\n\nSecond")

    @override_settings(ORA2_AI_ASSESSMENT={})
    @patch.dict("os.environ", {}, clear=True)
    def test_missing_api_key_is_configuration_error(self):
        with self.assertRaises(AIGradingConfigurationError):
            get_ai_grading_config()

    @override_settings(ORA2_AI_ASSESSMENT={"API_KEY": "test-key", "MODEL": "test-model"})
    @patch("openassessment.assessment.ai_client.urlopen")
    def test_grades_with_strict_structured_output(self, mock_urlopen):
        structured_result = {
            "criteria": {
                "accuracy": {"feedback": "Correct and clear.", "selected_option": "good"},
                "comments": {"feedback": "Add one concrete example."},
            },
            "overall_feedback": "Good response.",
        }
        mock_urlopen.return_value = FakeResponse({
            "id": "resp_test",
            "model": "test-model-2026-01-01",
            "status": "completed",
            "output": [{
                "type": "message",
                "content": [{"type": "output_text", "text": json.dumps(structured_result)}],
            }],
        })

        result = grade_essay("Testing catches regressions.", RUBRIC)

        self.assertEqual(result["assessment"], structured_result)
        self.assertEqual(result["response_id"], "resp_test")
        request = mock_urlopen.call_args.args[0]
        payload = json.loads(request.data.decode("utf-8"))
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])
        self.assertIn("Bearer test-key", request.headers.values())
        self.assertIn("Testing catches regressions.", payload["input"])

    @override_settings(ORA2_AI_ASSESSMENT={"API_KEY": "test-key"})
    @patch("openassessment.assessment.ai_client.urlopen")
    def test_rejects_option_outside_rubric(self, mock_urlopen):
        result = {
            "criteria": {
                "accuracy": {"feedback": "Invalid", "selected_option": "excellent"},
                "comments": {"feedback": "Feedback"},
            },
            "overall_feedback": "Feedback",
        }
        mock_urlopen.return_value = FakeResponse({
            "status": "completed",
            "output": [{"content": [{"type": "output_text", "text": json.dumps(result)}]}],
        })

        with self.assertRaises(AIGradingServiceError):
            grade_essay("An answer.", RUBRIC)
