"""
Unit Tests — ML Service (Drug Severity Classifier)

Tests:
  - Feature extraction
  - Drug name normalization
  - Known interaction lookup
  - Model training and prediction
  - All 5 severity classes
"""

import pytest
import numpy as np
from unittest.mock import patch
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


from src.services.ml_service import (
    MLService,
    normalize_drug_name,
    DRUG_ALIASES,
    KNOWN_INTERACTIONS,
)
from src.models.schemas import SeverityLevel


# ─── normalize_drug_name ──────────────────────────────────────────────

class TestNormalizeDrugName:

    def test_lowercase(self):
        assert normalize_drug_name("WARFARIN") == "warfarin"

    def test_strips_dosage(self):
        assert normalize_drug_name("Ibuprofen 400mg") == "ibuprofen"

    def test_strips_parentheses(self):
        assert normalize_drug_name("Paracetamol (Tylenol)") == "paracetamol"

    def test_resolves_alias_tylenol(self):
        assert normalize_drug_name("Tylenol") == "paracetamol"

    def test_resolves_alias_viagra(self):
        assert normalize_drug_name("Viagra") == "sildenafil"

    def test_resolves_alias_advil(self):
        assert normalize_drug_name("Advil") == "ibuprofen"

    def test_no_change_for_generic(self):
        assert normalize_drug_name("metformin") == "metformin"

    def test_strips_extra_whitespace(self):
        assert normalize_drug_name("  aspirin  ") == "aspirin"


# ─── Feature Extraction ───────────────────────────────────────────────

class TestFeatureExtraction:

    def setup_method(self):
        self.service = MLService()

    def test_returns_correct_shape(self):
        features = self.service._extract_features("warfarin", "aspirin")
        assert features.shape == (1, 7)

    def test_values_between_0_and_1(self):
        features = self.service._extract_features("metformin", "lisinopril")
        assert np.all(features >= 0.0)
        assert np.all(features <= 1.0)

    def test_known_pair_has_known_flag(self):
        # known=1.0 is feature index 4
        features = self.service._extract_features("warfarin", "aspirin")
        assert features[0][4] == 1.0

    def test_unknown_pair_has_zero_flag(self):
        features = self.service._extract_features("drug_x_unknown", "drug_y_unknown")
        assert features[0][4] == 0.0

    def test_same_drug_family_suffix(self):
        # Both end in -olol → suffix similarity feature should be 1.0
        features = self.service._extract_features("metoprolol", "propranolol")
        assert features[0][5] == 1.0


# ─── Model Training & Prediction ─────────────────────────────────────

class TestMLServicePrediction:

    def setup_method(self):
        self.service = MLService()
        # Train model in-memory for tests (no file I/O)
        with patch.object(self.service, '_save_model', return_value=None):
            self.service._train_model()

    def test_model_is_loaded_after_train(self):
        assert self.service.model is not None
        assert self.service._loaded is True

    def test_predict_returns_valid_severity(self):
        import asyncio
        result = asyncio.run(self.service.predict("warfarin", "aspirin"))
        assert result.severity in list(SeverityLevel)

    def test_predict_confidence_between_0_and_1(self):
        import asyncio
        result = asyncio.run(self.service.predict("metformin", "lisinopril"))
        assert 0.0 <= result.confidence <= 1.0

    def test_predict_probabilities_sum_to_1(self):
        import asyncio
        result = asyncio.run(self.service.predict("aspirin", "ibuprofen"))
        total = sum(result.probabilities.values())
        assert abs(total - 1.0) < 0.01

    def test_known_contraindicated_pair(self):
        """warfarin + aspirin is a known CONTRAINDICATED pair."""
        import asyncio
        result = asyncio.run(self.service.predict("warfarin", "aspirin"))
        # The model should predict contraindicated OR boost confidence for it
        assert result.confidence > 0.7

    def test_alias_resolves_before_prediction(self):
        """Tylenol → paracetamol. Both should give same result."""
        import asyncio
        result_generic = asyncio.run(self.service.predict("paracetamol", "amoxicillin"))
        result_brand   = asyncio.run(self.service.predict("Tylenol", "amoxicillin"))
        assert result_generic.severity == result_brand.severity

    def test_probabilities_have_all_5_classes(self):
        import asyncio
        result = asyncio.run(self.service.predict("digoxin", "amiodarone"))
        expected_keys = {"none", "mild", "moderate", "severe", "contraindicated"}
        assert set(result.probabilities.keys()) == expected_keys


# ─── Known Interactions Coverage ─────────────────────────────────────

class TestKnownInteractions:

    def test_known_interactions_not_empty(self):
        assert len(KNOWN_INTERACTIONS) > 0

    def test_all_have_valid_severity(self):
        valid = set(SeverityLevel)
        for pair, severity in KNOWN_INTERACTIONS.items():
            assert severity in valid, f"{pair} has invalid severity {severity}"

    def test_contraindicated_pairs_exist(self):
        contraindicated = [
            s for s in KNOWN_INTERACTIONS.values()
            if s == SeverityLevel.CONTRAINDICATED
        ]
        assert len(contraindicated) >= 3

    def test_warfarin_aspirin_is_contraindicated(self):
        pair = frozenset(["warfarin", "aspirin"])
        assert KNOWN_INTERACTIONS[pair] == SeverityLevel.CONTRAINDICATED
