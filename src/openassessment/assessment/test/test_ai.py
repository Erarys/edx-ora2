"""Tests for the AI assessment workflow API."""

from unittest.mock import patch

from django.test import override_settings
from submissions.api import create_submission

from openassessment.assessment.api.ai import (
    assessment_is_finished,
    create_assessment,
    get_assessment_scores_by_criteria,
    get_latest_assessment,
    get_score,
    on_init,
)
from openassessment.assessment.tasks import grade_essay_task
from openassessment.assessment.test.constants import RUBRIC, STUDENT_ITEM
from openassessment.test_utils import CacheResetTest


class AIAssessmentApiTest(CacheResetTest):
    """Verify native ORA assessment persistence and task scheduling."""

    def setUp(self):
        super().setUp()
        self.submission = create_submission(STUDENT_ITEM, {"text": "A test essay."})
        self.result = {
            "criteria": {
                RUBRIC["criteria"][0]["name"]: {
                    "feedback": "Strong vocabulary.",
                    "selected_option": RUBRIC["criteria"][0]["options"][2]["name"],
                },
                RUBRIC["criteria"][1]["name"]: {
                    "feedback": "Grammar needs work.",
                    "selected_option": RUBRIC["criteria"][1]["options"][1]["name"],
                },
            },
            "overall_feedback": "A useful response.",
        }

    def test_create_and_retrieve_assessment(self):
        assessment = create_assessment(self.submission["uuid"], RUBRIC, self.result, "test-model")

        self.assertEqual(assessment["score_type"], "AI")
        self.assertEqual(assessment["points_earned"], 3)
        self.assertEqual(assessment["points_possible"], 4)
        self.assertEqual(assessment["feedback"], "A useful response.")
        self.assertTrue(assessment_is_finished(self.submission["uuid"], {}, {}))
        self.assertEqual(get_latest_assessment(self.submission["uuid"])["id"], assessment["id"])
        self.assertEqual(get_score(self.submission["uuid"], {}, {})["points_earned"], 3)
        self.assertEqual(
            get_assessment_scores_by_criteria(self.submission["uuid"]),
            {
                RUBRIC["criteria"][0]["name"]: 2,
                RUBRIC["criteria"][1]["name"]: 1,
            },
        )

    def test_create_is_idempotent(self):
        first = create_assessment(self.submission["uuid"], RUBRIC, self.result, "test-model")
        second = create_assessment(self.submission["uuid"], RUBRIC, self.result, "test-model")

        self.assertEqual(first["id"], second["id"])

    @override_settings(ORA2_AI_ASSESSMENT={"API_KEY": "test-key"})
    @patch("openassessment.assessment.tasks.grade_essay_task.delay")
    def test_on_init_enqueues_after_commit(self, mock_delay):
        with self.captureOnCommitCallbacks(execute=True):
            on_init(self.submission["uuid"], RUBRIC)

        mock_delay.assert_called_once_with(self.submission["uuid"], RUBRIC)

    @patch("openassessment.assessment.tasks.assessment_complete_signal.send")
    @patch("openassessment.assessment.tasks.grade_essay")
    def test_task_grades_once_and_signals_completion(self, mock_grade_essay, mock_signal):
        mock_grade_essay.return_value = {
            "assessment": self.result,
            "model": "test-model",
            "response_id": "resp_test",
        }

        first_id = grade_essay_task.run(self.submission["uuid"], RUBRIC)
        second_id = grade_essay_task.run(self.submission["uuid"], RUBRIC)

        self.assertEqual(first_id, second_id)
        mock_grade_essay.assert_called_once_with("A test essay.", RUBRIC)
        mock_signal.assert_called_once_with(
            sender=grade_essay_task,
            submission_uuid=self.submission["uuid"],
        )
