import os
import subprocess

def clone_github_repo():
    repo_url = input("GitHub Repository Link দিন: ").strip()

    if not repo_url.startswith("https://github.com/"):
        print("❌ Invalid GitHub URL")
        return

    folder_name = repo_url.rstrip("/").split("/")[-1]

    print(f"📥 Downloading {folder_name}...")

    try:
        subprocess.run(
            ["git", "clone", repo_url, folder_name],
            check=True
        )

        print(f"✅ Download Complete!")
        print(f"📂 Saved in: {os.path.abspath(folder_name)}")

    except subprocess.CalledProcessError:
        print("❌ Download Failed!")
        print("Git install আছে কিনা চেক করুন।")

if __name__ == "__main__":
    clone_github_repo()