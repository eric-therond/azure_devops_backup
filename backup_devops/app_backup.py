import time
import base64
import os
import logging

from backup_devops.helpers import Helpers
from backup_devops.git_operations import GitOperations
from azure.devops.v7_0.git.models import GitRepositoryCreateOptions, GitMergeParameters
from azure.devops.v7_0.core.models import TeamProject
from azure.devops.connection import Connection
from msrest.authentication import BasicAuthentication

class AppBackup:  
    BASIC_BOARD_PROCESS_ID = "b8a3a935-7e91-48b8-a94c-606d37c3e9f2"

    TARGET_ORGA = os.getenv('AZDEVOPS_BACKUP_TARGET_ORGA') 
    SOURCE_ORGA = os.getenv('AZDEVOPS_BACKUP_SOURCE_ORGA')
    
    URL_TARGET_ORGA = f'https://dev.azure.com/{TARGET_ORGA}/'
    URL_SOURCE_ORGA = f'https://dev.azure.com/{SOURCE_ORGA}/'

    PAT_TARGET_ORGA = os.getenv('AZDEVOPS_BACKUP_PAT_TARGET_ORGA') 
    PAT_SOURCE_ORGA = os.getenv('AZDEVOPS_BACKUP_PAT_SOURCE_ORGA')

    PAT_TARGET_ORGA_B64 = base64.b64encode(bytes(PAT_TARGET_ORGA, 'utf-8'))
    PAT_SOURCE_ORGA_B64 = base64.b64encode(bytes(PAT_SOURCE_ORGA, 'utf-8'))
    
    CURRENT_DIRECTORY = os.path.dirname(os.path.realpath(__file__))
    TMP_DIRECTORY = os.path.join(CURRENT_DIRECTORY, "tmp") 

    TARGET = 1
    SOURCE = 2

    def __init__(self, polling_interval_seconds=5):
        conn_target = Connection(base_url=AppBackup.URL_TARGET_ORGA, creds=BasicAuthentication('', AppBackup.PAT_TARGET_ORGA))
        conn_source = Connection(base_url=AppBackup.URL_SOURCE_ORGA, creds=BasicAuthentication('', AppBackup.PAT_SOURCE_ORGA))

        self.core_target = conn_target.clients.get_core_client()
        self.core_source = conn_source.clients.get_core_client()

        self.git_target = conn_target.clients.get_git_client()
        self.git_source = conn_source.clients.get_git_client()

        self.operations_target = conn_target.clients.get_operations_client()
        self.operations_source = conn_source.clients.get_operations_client()

    def get_project_by_name(self, type, name):
        if type == AppBackup.TARGET:
            get_projects_response = self.core_target.get_projects()
        else:
            get_projects_response = self.core_source.get_projects()

        for project in get_projects_response:
            if project.name == name:
                return project

        return None


    def get_repo_by_name(self, type, project_id, name):
        if type == AppBackup.TARGET:
            get_repos_response = self.git_target.get_repositories(project_id)
        else:
            get_repos_response = self.git_source.get_repositories(project_id)

        for repo in get_repos_response:
            if repo.name == name:
                return repo

        return None

    def wait_for_long_running_operation(self, type, operation_id, interval_seconds=5):
        if type == AppBackup.TARGET:
            operation = self.operations_target.get_operation(operation_id)
        else:
            operation = self.operations_source.get_operation(operation_id)

        while not AppBackup.has_operation_completed(operation):
            time.sleep(interval_seconds)
            if type == AppBackup.TARGET:
                operation = self.operations_target.get_operation(operation_id)
            else:
                operation = self.operations_source.get_operation(operation_id)

        return operation

    @staticmethod
    def has_operation_completed(operation):
        status = operation.status.lower()
        return status in ('succeeded', 'failed', 'cancelled')

    def create_target_project(self, project):
        capabilities =  {
            "versioncontrol": {
                "sourceControlType": "Git"
            },
            "processTemplate": {
                "templateTypeId": AppBackup.BASIC_BOARD_PROCESS_ID
            }
        }

        teamproject = TeamProject(name=project.name, description=project.description, visibility=project.visibility, capabilities=capabilities)
        responsesop = self.core_target.queue_create_project(teamproject)

        return self.wait_for_long_running_operation(AppBackup.TARGET, responsesop.id)

    def create_target_repository(self, project, name):
        return self.git_target.create_repository(GitRepositoryCreateOptions(name=name, project=project), project=project.id)     
   
    def backup_organization(self):
        Helpers.create_dir(AppBackup.TMP_DIRECTORY)

        get_projects_response = self.core_source.get_projects()
        for project in get_projects_response:
            target_project = self.get_project_by_name(AppBackup.TARGET, project.name)
            if target_project is None:
                operation = self.create_target_project(project)
                if operation.status == "succeeded":
                    target_project = self.get_project_by_name(AppBackup.TARGET, project.name)

            if target_project is not None:
                Helpers.create_dir(os.path.join(AppBackup.TMP_DIRECTORY, target_project.name))
                repos = self.git_source.get_repositories(project.id)
                for repo in repos:
                    target_repo = self.get_repo_by_name(AppBackup.TARGET, target_project.id, repo.name)
                    if target_repo is None:
                        op = self.create_target_repository(target_project, repo.name)
                        target_repo = self.get_repo_by_name(AppBackup.TARGET, target_project.id, repo.name)

                    if target_repo is not None:    
                        try: 
                            git_repo = GitOperations.clone_repository(AppBackup.TMP_DIRECTORY, AppBackup.SOURCE_ORGA, AppBackup.PAT_SOURCE_ORGA, target_project, target_repo)
                            if len(git_repo.heads) > 0:  
                                GitOperations.update_remote_target(AppBackup.TMP_DIRECTORY, AppBackup.TARGET_ORGA, AppBackup.PAT_TARGET_ORGA, target_project, target_repo)
                                GitOperations.push_all_branches(AppBackup.TMP_DIRECTORY, target_project, target_repo)

                        except Exception as err:
                            logging.error(f"Unexpected {err=}, {type(err)=}")

            break

                        
