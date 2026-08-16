"""ArtifactStore is abstract -- this just guards against someone dropping an
@abstractmethod and silently making it instantiable."""

import pytest

from src.services.artifact_store import ArtifactStore


def test_cannot_instantiate_abstract_class_directly():
    with pytest.raises(TypeError):
        ArtifactStore()
