import json
from pathlib import Path

from src.processing_profiles import ProcessingProfile


CONFIG_PATH = Path("config/processing-profiles.json")


def test_python_processing_profiles_match_shared_contract():
    payload = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["profiles"]["general"] == ProcessingProfile().to_dict()
    assert payload["profiles"]["parent_child"] == ProcessingProfile.parent_child().to_dict()
    assert payload["profiles"]["resume_semantic"] == ProcessingProfile.resume_semantic().to_dict()
