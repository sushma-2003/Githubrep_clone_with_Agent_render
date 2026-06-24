import importlib
import os
import subprocess

Repo = None

try:
    git = importlib.import_module("git")
    Repo = git.Repo
except ImportError:
    Repo = None


def clone_repository(repo_url):
    repo_name = repo_url.split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    local_path = os.path.join("repos", repo_name)

    if os.path.exists(local_path):
        print("Repository already cloned. Pulling latest changes...")

        try:
            if Repo is not None:
                repo = Repo(local_path)
                repo.remotes.origin.pull()
                print("Repository updated.")
            else:
                subprocess.run(
                    ["git", "-C", local_path, "pull"],
                    check=True
                )
        except Exception as e:
            print(f"Could not pull latest changes: {e}")
            print("Proceeding with existing local copy.")
    else:
        print("Cloning repository...")

        if Repo is not None:
            Repo.clone_from(repo_url, local_path)
        else:
            subprocess.run(
                ["git", "clone", repo_url, local_path],
                check=True
            )

    return local_path