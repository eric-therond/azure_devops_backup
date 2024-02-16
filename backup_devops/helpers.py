import os
import shutil
import stat
import platform

class Helpers:    
    @staticmethod
    def create_dir(mydir):
        if os.path.isdir(mydir) == False:
            os.mkdir(mydir)

    @staticmethod
    def delete_dir(mydir):
        if os.path.isdir(mydir):
            # some .git files are read only
            # https://stackoverflow.com/questions/58878089/how-to-remove-git-repository-in-python-on-windows
            if platform.system() == "Windows":
                for root, dirs, files in os.walk(mydir):  
                    for dir_ in dirs:
                        os.chmod(os.path.join(root, dir_), stat.S_IRWXU)
                    for file in files:
                        os.chmod(os.path.join(root, file), stat.S_IRWXU)

            shutil.rmtree(mydir, ignore_errors=True)
