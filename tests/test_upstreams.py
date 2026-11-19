from pathlib import Path
import tempfile
import unittest

from tools.upstreams import (LOCK, SourceError, git_hash, read_lock, safe_path,
                             select_projects, tree_hash, verify_tree)


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.data = b"Every original line.\nSecond line.\n"
        self.manifest = {"files": [["src/example.py", "100644", git_hash("blob", self.data), len(self.data)]], "gitlinks": []}

    def tearDown(self):
        self.temp.cleanup()

    def populate(self):
        (self.root / "src").mkdir()
        (self.root / "src/example.py").write_bytes(self.data)

    def test_complete_tree_roundtrip(self):
        self.populate()
        self.assertEqual(verify_tree(self.root, self.manifest)["filesVerified"], 1)

    def test_blob_matches_git_known_empty_object(self):
        self.assertEqual(git_hash("blob", b""), "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391")

    def test_empty_tree_matches_git(self):
        self.assertEqual(tree_hash([], []), "4b825dc642cb6eb9a060e54bf8d69288fbee4904")

    def test_file_tamper_is_not_silently_kept(self):
        self.populate()
        (self.root / "src/example.py").write_bytes(b"x" * len(self.data))
        with self.assertRaisesRegex(SourceError, "Changed source"):
            verify_tree(self.root, self.manifest)

    def test_missing_file_fails(self):
        with self.assertRaisesRegex(SourceError, "Missing 1"):
            verify_tree(self.root, self.manifest)

    def test_unexpected_file_fails(self):
        (self.root / "extra").write_text("unexpected")
        with self.assertRaisesRegex(SourceError, "Unexpected"):
            verify_tree(self.root, self.manifest)

    def test_symlink_fails(self):
        (self.root / "link").symlink_to(self.root)
        with self.assertRaisesRegex(SourceError, "symlink"):
            verify_tree(self.root, self.manifest)

    def test_traversal_and_git_metadata_are_rejected(self):
        for value in ("../outside", "/absolute", "a/../outside", "a/.git/config", "a//b", "a\\b", "./a", "a/"):
            with self.subTest(value=value), self.assertRaises(SourceError):
                safe_path(value)

    def test_inert_symlink_blob_keeps_target_bytes(self):
        data = b"/etc/shadow"
        manifest = {"files": [["link", "120000", git_hash("blob", data), len(data)]], "gitlinks": []}
        (self.root / "link").write_bytes(data)
        self.assertEqual(verify_tree(self.root, manifest)["symlinkBlobsAsText"], 1)
        self.assertFalse((self.root / "link").is_symlink())

    def test_lfs_pointer_is_not_claimed_as_materialized_payload(self):
        data = b'version https://git-lfs.github.com/spec/v1\noid sha256:' + b'a' * 64 + b'\nsize 12345\n'
        manifest = {'files': [['fixture.lfs', '100644', git_hash('blob', data), len(data)]], 'gitlinks': []}
        (self.root / 'fixture.lfs').write_bytes(data)
        report = verify_tree(self.root, manifest)
        self.assertEqual(report['gitLfsPointerFiles'], 1)
        self.assertEqual(report['gitLfsUniqueObjectsNotFetched'], 1)
        self.assertEqual(report['gitLfsUniquePayloadBytesNotFetched'], 12345)

    def test_executable_bit_is_verified(self):
        self.populate()
        self.manifest["files"][0][1] = "100755"
        with self.assertRaisesRegex(SourceError, "executable bit"):
            verify_tree(self.root, self.manifest)

    def test_tree_collision_fails(self):
        files = [["src", "100644", git_hash("blob", b""), 0], self.manifest["files"][0]]
        with self.assertRaisesRegex(SourceError, "collision"):
            tree_hash(files, [])

    def test_duplicate_entry_fails(self):
        with self.assertRaisesRegex(SourceError, "Duplicate"):
            tree_hash(self.manifest["files"] * 2, [])

    def test_lock_reproduces_every_upstream_git_tree(self):
        lock = read_lock(LOCK)
        self.assertEqual(len(lock["projects"]), 7)
        self.assertEqual(sum(p["fileCount"] for p in lock["projects"].values()), 22839)
        for project in lock["projects"].values():
            manifest = project["_manifest"]
            self.assertEqual(tree_hash(manifest["files"], manifest["gitlinks"]), project["tree"])

    def test_rea_selection_includes_all_five_submodules(self):
        selected = select_projects(read_lock(), ["rea"])
        self.assertEqual(len(selected), 6)
        self.assertNotIn("openmausbot", selected)

    def test_unknown_project_fails(self):
        with self.assertRaisesRegex(SourceError, "Unknown project"):
            select_projects(read_lock(), ["not-a-project"])


if __name__ == "__main__":
    unittest.main()
