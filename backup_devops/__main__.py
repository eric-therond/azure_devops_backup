from backup_devops.app_backup import AppBackup
import logging
        
def main():
    logging.basicConfig(level = logging.INFO)
    app_backup = AppBackup()
    app_backup.backup_organization()

if __name__ == "__main__":
    main()