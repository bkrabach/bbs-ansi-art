"""Pytest configuration for external test files."""

import os
from pathlib import Path
from typing import Optional

import pytest


def get_test_art_dir() -> Optional[Path]:
    """
    Get external art directory from environment or default locations.
    
    Set BBS_ANSI_ART_TEST_DIR environment variable to specify a custom location.
    """
    # Check environment variable first
    if env_path := os.environ.get("BBS_ANSI_ART_TEST_DIR"):
        path = Path(env_path).expanduser()
        if path.exists():
            return path

    # Check common default locations
    defaults = [
        Path.home() / "Downloads",  # Will filter for .ans files
        Path.home() / "ansi-art",
        Path.home() / "Documents" / "ansi-art",
    ]

    for default in defaults:
        if default.exists():
            # Verify it has .ans files
            ans_files = list(default.glob("*.ans"))[:1]
            if ans_files:
                return default

    return None


@pytest.fixture(scope="session")
def test_art_dir() -> Path:
    """Fixture providing external art directory, skips if unavailable."""
    art_dir = get_test_art_dir()
    if art_dir is None:
        pytest.skip(
            "External art directory not found. "
            "Set BBS_ANSI_ART_TEST_DIR or place .ans files in ~/Downloads"
        )
    return art_dir


@pytest.fixture(scope="session")
def sample_ans_files(test_art_dir: Path) -> list[Path]:
    """Get list of .ans files for testing."""
    files = list(test_art_dir.glob("*.ans"))
    if not files:
        pytest.skip(f"No .ans files found in {test_art_dir}")
    # Limit to avoid very slow tests
    return sorted(files)[:50]


@pytest.fixture
def single_ans_file(sample_ans_files: list[Path]) -> Path:
    """Get a single .ans file for quick tests."""
    return sample_ans_files[0]


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Generate test cases from fixtures."""
    if "ans_file" in metafunc.fixturenames:
        art_dir = get_test_art_dir()
        if art_dir:
            files = sorted(art_dir.glob("*.ans"))[:50]
            metafunc.parametrize("ans_file", files, ids=lambda p: p.name)
