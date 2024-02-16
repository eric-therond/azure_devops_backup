import time
import os
import logging

from backup_devops.helpers import Helpers
from backup_devops.git_operations import GitOperations
from azure.devops.v7_0.git.models import GitRepositoryCreateOptions
from azure.devops.v7_0.core.models import TeamProject
from azure.devops.v7_0.work_item_tracking.models import Wiql, CommentCreate
from azure.devops.v7_0.work_item_tracking import JsonPatchOperation
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
    
    TMP_DIRECTORY = os.path.join(os.getcwd(), "tmp") 

    TARGET = 1
    SOURCE = 2

    def __init__(self):
        conn_target = Connection(base_url=AppBackup.URL_TARGET_ORGA, creds=BasicAuthentication('', AppBackup.PAT_TARGET_ORGA))
        conn_source = Connection(base_url=AppBackup.URL_SOURCE_ORGA, creds=BasicAuthentication('', AppBackup.PAT_SOURCE_ORGA))

        self.core_target = conn_target.clients.get_core_client()
        self.core_source = conn_source.clients.get_core_client()

        self.git_target = conn_target.clients.get_git_client()
        self.git_source = conn_source.clients.get_git_client()

        self.operations_target = conn_target.clients.get_operations_client()
        self.operations_source = conn_source.clients.get_operations_client()

        self.work_item_target = conn_target.clients.get_work_item_tracking_client()
        self.work_item_source = conn_source.clients.get_work_item_tracking_client()

    def get_work_item_client(self, type):
        if type == AppBackup.TARGET:    
            return self.work_item_target
        else:
            return self.work_item_source

    def get_operations_client(self, type):
        if type == AppBackup.TARGET:    
            return self.operations_target
        else:
            return self.operations_source

    def get_git_client(self, type):
        if type == AppBackup.TARGET:    
            return self.git_target
        else:
            return self.git_source

    def get_core_client(self, type):
        if type == AppBackup.TARGET:    
            return self.core_target
        else:
            return self.core_source
    
    # https://stackoverflow.com/questions/76104090/using-the-azure-devops-python-api-to-create-a-new-work-item
    @staticmethod  
    def create_work_item_field_patch_operation(op, field, value):
        path = '/fields/{field}'.format(field=field)
        return AppBackup.create_patch_operation(op=op, path=path, value=value)

    @staticmethod  
    def create_patch_operation(op, path, value):
        patch_operation = JsonPatchOperation()
        patch_operation.op = op
        patch_operation.path = path
        patch_operation.value = value
        patch_operation._from = None
        return patch_operation

    def delete_work_items(self, type, project_id, work_items):
        wit_client = self.get_work_item_client(type)

        for work_item in work_items:
            wit_client.delete_work_item(work_item["id"], project=project_id, destroy=True)


    def backup_work_items(self, type, project_id, work_items):
        wit_client = self.get_work_item_client(type)

        i = 0
        for work_item in work_items:
            i = i + 1
            patch_document = []
            if "System.Title" in work_item["fields"]:
                patch_document.append(AppBackup.create_work_item_field_patch_operation('add', 'System.Title', work_item["fields"]["System.Title"]))

            if "System.Description" in work_item["fields"]:
                patch_document.append(AppBackup.create_work_item_field_patch_operation('add', 'System.Description', work_item["fields"]["System.Description"]))

            if "System.State" in work_item["fields"]:
                patch_document.append(AppBackup.create_work_item_field_patch_operation('add', 'System.State', work_item["fields"]["System.State"]))

            wit_created = wit_client.create_work_item(
                document=patch_document,
                project=project_id,
                type=work_item["fields"]["System.WorkItemType"]
            ).as_dict()

            for comment in work_item["comments"]:
                wit_client.add_comment(CommentCreate(comment["text"]), project_id, wit_created["id"])
    
    def query_work_items(self, type, project_name):
        wiql = Wiql(f"select [System.Id] from WorkItems where [System.TeamProject] = '{project_name}'")

        wit_client = self.get_work_item_client(type)

        wits = []
        wiql_results = wit_client.query_by_wiql(wiql).work_items
        if wiql_results:
            for wiql_result in wiql_results:
                wit_id = int(wiql_result.id)
                wit = wit_client.get_work_item(wit_id).as_dict()

                comments_wit = []
                comments_list = wit_client.get_comments(project_name, wit_id).as_dict()
                for comment in comments_list["comments"]:
                    comments_wit.append(comment)

                wit["comments"] = comments_wit
                wits.append(wit)

        return wits

    def get_project_by_name(self, type, name):
        core_client = self.get_core_client(type)
        get_projects_response = core_client.get_projects()

        for project in get_projects_response:
            if project.name == name:
                return project

        return None

    def get_repo_by_name(self, type, project_id, name):
        git_client = self.get_git_client(type)
        get_repos_response = git_client.get_repositories(project_id)

        for repo in get_repos_response:
            if repo.name == name:
                return repo

        return None

    def wait_for_long_running_operation(self, type, operation_id, interval_seconds=5):
        operations_client = self.get_operations_client(type)
        operation = operations_client.get_operation(operation_id)

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
                logging.info(f"project name {target_project.name} is being backed up")
                # the projects and repositories are saved in target
                Helpers.create_dir(os.path.join(AppBackup.TMP_DIRECTORY, target_project.name))
                repos = self.git_source.get_repositories(project.id)
                for repo in repos:
                    target_repo = self.get_repo_by_name(AppBackup.TARGET, target_project.id, repo.name)
                    if target_repo is None:
                        self.create_target_repository(target_project, repo.name)
                        target_repo = self.get_repo_by_name(AppBackup.TARGET, target_project.id, repo.name)

                    if target_repo is not None:    
                        try:
                            git_repo = GitOperations.clone_repository(AppBackup.TMP_DIRECTORY, AppBackup.SOURCE_ORGA, AppBackup.PAT_SOURCE_ORGA, target_project, target_repo)
                            if len(git_repo.heads) > 0:  
                                GitOperations.update_remote_target(AppBackup.TMP_DIRECTORY, AppBackup.TARGET_ORGA, AppBackup.PAT_TARGET_ORGA, target_project, target_repo)
                                GitOperations.push_all_branches(AppBackup.TMP_DIRECTORY, target_project, target_repo)

                        except Exception as err:
                            logging.error(f"Unexpected {err=}, {type(err)=}")

                # the work items are saved in target
                work_items_source = self.query_work_items(AppBackup.SOURCE, project.name)
                work_items_target = self.query_work_items(AppBackup.TARGET, project.name)
                self.delete_work_items(AppBackup.TARGET, target_project.id, work_items_target)
                self.backup_work_items(AppBackup.TARGET, target_project.id, work_items_source)

        Helpers.delete_dir(AppBackup.TMP_DIRECTORY)
