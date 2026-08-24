import json
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "data-ci.yml"
BACKEND_CROSSWALK_PATH = (
    REPO_ROOT / "data" / "config" / "handoff" / "backend_import_crosswalk.json"
)
RAG_CASES_PATH = (
    REPO_ROOT / "data" / "config" / "rag" / "jac104_retrieval_cases.json"
)


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _workflow_path_sections(workflow: str) -> tuple[str, str]:
    pull_request = workflow.split("  pull_request:\n", 1)[1].split(
        "  push:\n", 1
    )[0]
    push = workflow.split("  push:\n", 1)[1].split("\npermissions:\n", 1)[0]
    return pull_request, push


class DataCiDependencyPathTests(unittest.TestCase):
    def required_repository_dependencies(self) -> set[str]:
        crosswalk = _load_json(BACKEND_CROSSWALK_PATH)
        rag_cases = _load_json(RAG_CASES_PATH)

        dependencies = {
            source["path"]
            for source in crosswalk["backend_sources"].values()
        }
        dependencies.add(
            crosswalk["verification"]["actual"]["evidence"]
            ["runtime_document"]["path"]
        )
        dependencies.add(
            rag_cases["ai_execution"]["result_manifest"]["path"]
        )
        dependencies.add(
            rag_cases["ai_execution"]["index_manifest"]["path"]
        )
        return dependencies

    def test_pull_request_and_push_watch_actual_data_dependencies(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        pull_request, push = _workflow_path_sections(workflow)

        for dependency in sorted(self.required_repository_dependencies()):
            entry = f'- "{dependency}"'
            with self.subTest(dependency=dependency, event="pull_request"):
                self.assertIn(entry, pull_request)
            with self.subTest(dependency=dependency, event="push"):
                self.assertIn(entry, push)

    def test_dependency_triggers_do_not_watch_whole_service_trees(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        pull_request, push = _workflow_path_sections(workflow)

        for broad_path in ('- "backend/**"', '- "ai/**"', '- "docs/**"'):
            with self.subTest(path=broad_path, event="pull_request"):
                self.assertNotIn(broad_path, pull_request)
            with self.subTest(path=broad_path, event="push"):
                self.assertNotIn(broad_path, push)

    def test_data_ci_installs_pinned_schema_validation_dependencies(self) -> None:
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn('python-version: "3.13.13"', workflow)
        self.assertIn(
            "--constraint backend/requirements/constraints-py313.txt",
            workflow,
        )
        self.assertIn("PyYAML==6.0.3", workflow)
        self.assertIn("jsonschema==4.26.0", workflow)


if __name__ == "__main__":
    unittest.main()
