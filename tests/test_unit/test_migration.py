"""Unit tests for migration tools."""
import pytest
from server.tools.migration import PrepareMigrationInput, CompleteMigrationInput


class TestMigrationInput:
    def test_valid_prepare(self):
        params = PrepareMigrationInput(
            project_name="my-project",
            migration_sql="ALTER TABLE users ADD COLUMN age INT",
            description="Add age column",
        )
        assert "ALTER TABLE" in params.migration_sql

    def test_complete_apply(self):
        params = CompleteMigrationInput(
            project_name="my-project",
            migration_branch="migration-abc123",
            apply=True,
        )
        assert params.apply is True

    def test_complete_discard(self):
        params = CompleteMigrationInput(
            project_name="my-project",
            migration_branch="migration-abc123",
            apply=False,
        )
        assert params.apply is False
