from __future__ import annotations

import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest import mock

import yaml


WEBSITE_ROOT = Path(__file__).resolve().parents[1]
MATERIALS_ROOT = WEBSITE_ROOT.parent / "materials"


def load_manager():
    spec = importlib.util.spec_from_file_location(
        "qmsbr_split_manager_tests", WEBSITE_ROOT / "tools/manage.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load website/tools/manage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


manage = load_manager()


class SplitPublicationWorkflowTests(unittest.TestCase):
    def test_release_scope_is_exactly_four_chapters_one_note_no_supplements(self):
        model = manage.load_model(MATERIALS_ROOT)
        self.assertEqual(
            model["module_ids"],
            ["part1-ch01", "part1-ch02", "part1-ch03", "part1-ch04"],
        )
        self.assertEqual(model["note_ids"], ["part1-ch01"])
        manifest = manage.manifest_document(model)
        self.assertEqual(manifest["supplement_ids"], [])
        self.assertEqual(len(manifest["render_targets"]), 4)
        self.assertEqual(len(manifest["copied_resources"]), 5)

    def test_render_only_inputs_have_no_public_paths(self):
        model = manage.load_model(MATERIALS_ROOT)
        manifest = manage.manifest_document(model)
        for path in manifest["render_only_inputs"]:
            self.assertIn(path, manifest["material_inputs"])
            self.assertNotIn(path, manifest["copied_resources"])
            self.assertNotIn(path, manifest["required_outputs"])

    def test_approved_context_hashes_still_match_finalized_materials(self):
        model = manage.load_model(MATERIALS_ROOT)
        approvals = model["approvals"]["approved_render_contexts"]
        self.assertEqual(model["render_context_hashes"], approvals)

    def test_library_has_three_columns_and_no_computing_download_column(self):
        model = manage.load_model(MATERIALS_ROOT)
        fragment = manage.public_fragments(model)[
            "library/_generated/library.qmd"
        ].decode("utf-8")
        self.assertIn("<th>No.</th><th>Chapter</th><th>Formats</th>", fragment)
        self.assertEqual(fragment.count("Read online"), 4)
        self.assertEqual(fragment.count("Download PDF"), 4)
        self.assertNotIn("Computing supplements", fragment)

    def test_normalize_relative_rejects_traversal_globs_and_windows_devices(self):
        for candidate in (
            "../private.qmd", "supplement/*.csv", "CON/file.txt", "NUL.txt",
            "nested//file.txt", "bad:name.txt", "nested\\file.txt", "control\x01.txt",
        ):
            with self.subTest(candidate=candidate):
                with self.assertRaises(manage.PublicationError):
                    manage.normalize_relative(candidate, "test path")

    def test_link_check_rejects_local_file_uris(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-link-policy-") as raw:
            root = Path(raw)
            for href in (
                "file:///C:/private/notes.docx", "C:/private/notes.docx",
                "javascript:alert(1)", "http://localhost:8000/private",
                "https://127.0.0.1/private", "//192.168.1.10/private",
                "https://10.0.0.4/private", "https://intranet/private",
            ):
                with self.subTest(href=href):
                    (root / "index.html").write_text(
                        f'<a href="{href}">private</a>', encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        manage.PublicationError, "Broken internal links",
                    ):
                        manage.check_links(root)

    def test_website_policy_rejects_a_material_pdf(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-source-policy-") as raw:
            root = Path(raw)
            (root / "src").mkdir()
            (root / "src/index.qmd").write_text("---\ntitle: Test\n---\n", encoding="utf-8")
            (root / "src/chapter.pdf").write_bytes(b"%PDF-test")
            policy = {
                "allowed_roots": ["src"],
                "allowed_root_files": ["policy.yml"],
                "forbidden_roots": [],
                "forbidden_extensions": [".pdf"],
            }
            policy_path = root / "policy.yml"
            policy_path.write_text(yaml.safe_dump(policy), encoding="utf-8")
            with self.assertRaisesRegex(manage.PublicationError, "Forbidden file type"):
                manage.validate_source_repository(root, policy_path)

    def test_exact_source_policy_rejects_an_unlisted_nested_file(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-exact-source-policy-") as raw:
            root = Path(raw)
            (root / "src").mkdir()
            (root / "src/index.qmd").write_text("---\ntitle: Test\n---\n", encoding="utf-8")
            (root / "src/private.docx").write_bytes(b"private")
            policy_path = root / "policy.yml"
            policy_path.write_text(
                yaml.safe_dump({
                    "allowed_files": ["policy.yml", "src/index.qmd"],
                    "forbidden_extensions": [".docx"],
                }),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(manage.PublicationError, "unexpected: src/private.docx"):
                manage.validate_source_repository(root, policy_path)

    def test_portable_quarto_download_is_pinned(self):
        self.assertEqual(manage.QUARTO_WINDOWS_SIZE, 148_278_833)
        self.assertEqual(
            manage.QUARTO_WINDOWS_SHA256,
            "4e824652ff0da3f646868277582ed59c0872d1456e35350b7d7cdc4243ee18c2",
        )

    def test_pyyaml_release_dependency_is_pinned_and_active(self):
        self.assertEqual(manage.PY_YAML_VERSION, "6.0.3")
        manage.check_python_environment()
        requirements = (WEBSITE_ROOT / "requirements-release.txt").read_text(encoding="utf-8")
        self.assertIn("PyYAML==6.0.3", requirements)
        self.assertIn(
            "79005a0d97d5ddabfeeea4cf676af11e647e41d81c9a7722a193022accdb6b7c",
            requirements,
        )

    def test_citation_cff_uses_a_valid_top_level_type(self):
        citation = manage.load_yaml(WEBSITE_ROOT / "CITATION.cff")
        self.assertEqual(citation.get("cff-version"), "1.2.0")
        self.assertIn(citation.get("type"), {"dataset", "software"})
        self.assertEqual(citation.get("type"), "software")

    def test_staged_input_mutation_is_rejected(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-stage-integrity-") as raw:
            root = Path(raw)
            staged = root / "project"
            staged.mkdir()
            target = staged / "chapters/chapter_01.pdf"
            target.parent.mkdir()
            target.write_bytes(b"approved")
            previous = manage.PROJECT_ROOT
            manage.PROJECT_ROOT = staged
            try:
                expected = {
                    "chapters/chapter_01.pdf": manage.sha256_bytes(b"approved"),
                }
                manage.verify_staged_inputs(expected)
                target.write_bytes(b"changed by renderer")
                with self.assertRaisesRegex(
                    manage.PublicationError, "modified during rendering",
                ):
                    manage.verify_staged_inputs(expected)
            finally:
                manage.PROJECT_ROOT = previous

    def test_atomic_publisher_write_does_not_modify_a_hardlinked_target(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-hardlink-") as raw:
            root = Path(raw)
            outside = root / "outside.txt"
            destination = root / "destination.txt"
            outside.write_bytes(b"outside remains unchanged")
            try:
                destination.hardlink_to(outside)
            except OSError as exc:
                self.skipTest(f"Hard links are unavailable: {exc}")
            manage.atomic_write(destination, b"new public bytes")
            self.assertEqual(outside.read_bytes(), b"outside remains unchanged")
            self.assertEqual(destination.read_bytes(), b"new public bytes")

    def test_work_root_link_is_rejected_before_cleanup(self):
        with tempfile.TemporaryDirectory(prefix="qmsbr-work-root-") as raw:
            root = Path(raw)
            website = root / "website"
            work = website / ".qmsbr"
            website.mkdir()
            work.mkdir()
            previous_website = manage.WEBSITE_ROOT
            previous_work = manage.WORK_ROOT
            manage.WEBSITE_ROOT = website
            manage.WORK_ROOT = work
            try:
                with mock.patch.object(manage, "is_link_or_junction", return_value=True):
                    with self.assertRaisesRegex(
                        manage.PublicationError, "must not be a link or junction",
                    ):
                        manage.ensure_work_root()
            finally:
                manage.WEBSITE_ROOT = previous_website
                manage.WORK_ROOT = previous_work


if __name__ == "__main__":
    unittest.main()
