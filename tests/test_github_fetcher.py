import tempfile
import unittest
from pathlib import Path

from portfolio_fit.github_fetcher import GitHubRepoFetcher


class GitHubRepoFetcherTests(unittest.TestCase):
    def test_filter_supported_repos_includes_jupyter_primary_language(self):
        with tempfile.TemporaryDirectory() as tmp:
            fetcher = GitHubRepoFetcher(username="demo", output_dir=Path(tmp))
            repos = [
                {"name": "nb_repo", "language": "Jupyter Notebook"},
                {"name": "py_repo", "language": "Python"},
                {"name": "cpp_repo", "language": "C++"},
                {"name": "unknown_repo", "language": None},
            ]

            filtered = fetcher.filter_supported_repos(repos)
            names = [repo["name"] for repo in filtered]

            self.assertIn("nb_repo", names)
            self.assertIn("py_repo", names)
            self.assertIn("unknown_repo", names)
            self.assertNotIn("cpp_repo", names)

    def test_supported_repo_path_accepts_ipynb_sources(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo_nb"
            (repo / ".git").mkdir(parents=True)
            (repo / "analysis.ipynb").write_text(
                '{"cells":[{"cell_type":"code","source":["print(1)\\n"]}]}',
                encoding="utf-8",
            )

            fetcher = GitHubRepoFetcher(username="demo", output_dir=Path(tmp))
            self.assertTrue(fetcher._is_supported_repo_path(repo))


if __name__ == "__main__":
    unittest.main()
