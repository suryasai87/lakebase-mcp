"""Unit tests for branching tools."""
import pytest
from server.tools.branching import CreateBranchInput, DeleteBranchInput


class TestBranchInputValidation:
    def test_valid_branch_creation(self):
        params = CreateBranchInput(
            project_name="my-project", branch_name="feature-auth"
        )
        assert params.branch_name == "feature-auth"
        assert params.parent_branch is None

    def test_branch_with_parent(self):
        params = CreateBranchInput(
            project_name="my-project",
            branch_name="sub-feature",
            parent_branch="feature-auth",
        )
        assert params.parent_branch == "feature-auth"


class TestDeleteBranchValidation:
    def test_valid_delete(self):
        params = DeleteBranchInput(
            project_name="my-project", branch_name="old-branch"
        )
        assert params.branch_name == "old-branch"
