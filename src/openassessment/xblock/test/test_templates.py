""" Tests for openassessment templates """

from unittest import TestCase
from openassessment.xblock.openassesment_template_mixin import OpenAssessmentTemplatesMixin


class TemplatesMixin(TestCase):
    """
    Tests for openassessment templates
    """

    def setUp(self):
        super().setUp()
        self.block = OpenAssessmentTemplatesMixin()

    def test_templates(self):
        templates = self.block.templates()
        self.assertEqual(len(templates), 6)
        self.assertIn('ai-assessment', {template['template_id'] for template in templates})
        for template in templates:
            self.assertIsInstance(template, dict)
            self.assertIn('template_id', template)

    def test_template_filter(self):
        for template in self.block.templates():
            is_not_peer = template['template_id'] != 'peer-assessment'
            self.assertEqual(is_not_peer, self.block.filter_templates(template, None))
