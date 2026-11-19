"""Éléments communs aux tests."""

import sys
from pathlib import Path

import pytest

# Permet de lancer « pytest » depuis la racine sans installer le paquet
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from inventaire.base import Base  # noqa: E402


@pytest.fixture
def base(tmp_path):
    """Base SQLite vide, dans un dossier temporaire."""
    b = Base(str(tmp_path / "test.db"))
    yield b
    b.fermer()
