from backup_devops.git_operations import GitOperations
from backup_devops.app_backup import AppBackup
        
def main():
    app_backup = AppBackup()
    app_backup.backup_organization()
    #AppBackup.delete_dir(GitOperations.REPOS_DIRECTORY)

if __name__ == "__main__":
    main()