import os
from git import Repo
from backup_devops.helpers import Helpers
import time

class GitOperations:
    @staticmethod  
    def clone_repository(tmp_dir, orga_name, pat_orga, project, repo):
        repo_dir = os.path.join(tmp_dir, project.name, repo.name)

        # in case the repository exists we delete it
        Helpers.delete_dir(repo_dir)
        # we create the target dir
        Helpers.create_dir(repo_dir)

        remote = f"https://{pat_orga}@dev.azure.com/{orga_name}/{project.name}/_git/{repo.name}"
        return Repo.clone_from(remote, repo_dir)
       
    @staticmethod  
    def update_remote_target(tmp_dir, orga_name, pat_orga, project, repo): 
        repo_dir = os.path.join(tmp_dir, project.name, repo.name)

        git_repo = Repo.init(repo_dir)

        remote_url = f"https://{pat_orga}@dev.azure.com/{orga_name}/{project.name}/_git/{repo.name}"
        git_repo.delete_remote("origin")
        git_repo.create_remote("origin", url=remote_url)
       
    @staticmethod  
    def push_all_branches(tmp_dir, project, repo): 
        repo_dir = os.path.join(tmp_dir, project.name, repo.name)

        git_repo = Repo(repo_dir)

        git_repo.git.push(all=True)