"""Unit tests for compute management tools (Gap 3)."""
import pytest
from server.tools.compute import (
    ConfigureAutoscalingInput,
    ConfigureScaleToZeroInput,
    CreateReadReplicaInput,
)


class TestAutoscalingValidation:
    def test_valid_autoscaling_config(self):
        params = ConfigureAutoscalingInput(
            project_name="my-project",
            min_cu=1.0,
            max_cu=8.0,
        )
        assert params.min_cu == 1.0
        assert params.max_cu == 8.0

    def test_min_cu_lower_bound(self):
        with pytest.raises(ValueError):
            ConfigureAutoscalingInput(
                project_name="my-project", min_cu=0.1, max_cu=4.0
            )

    def test_max_cu_upper_bound(self):
        with pytest.raises(ValueError):
            ConfigureAutoscalingInput(
                project_name="my-project", min_cu=1.0, max_cu=64.0
            )


class TestScaleToZeroValidation:
    def test_valid_config(self):
        params = ConfigureScaleToZeroInput(
            project_name="my-project",
            enabled=True,
            timeout_seconds=300,
        )
        assert params.enabled is True
        assert params.timeout_seconds == 300

    def test_timeout_lower_bound(self):
        with pytest.raises(ValueError):
            ConfigureScaleToZeroInput(
                project_name="my-project", enabled=True, timeout_seconds=10
            )

    def test_timeout_upper_bound(self):
        with pytest.raises(ValueError):
            ConfigureScaleToZeroInput(
                project_name="my-project", enabled=True, timeout_seconds=7200
            )


class TestReadReplicaValidation:
    def test_valid_replica(self):
        params = CreateReadReplicaInput(
            project_name="my-project", min_cu=0.5, max_cu=4.0
        )
        assert params.min_cu == 0.5
        assert params.branch_name == "production"
