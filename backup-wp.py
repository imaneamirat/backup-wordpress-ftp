#!/usr/bin/python3

###########################################################
#
# This python script is used to backup Wordpress website and associated mysql database
# using mysqldump and tar utility.
# Backups are copied to FTP server
# and encrypted using a private AES-256 key
# Needs privileges to access Wordpress site files and Wordpress database
# and write access to backup local folders
# ie to be executed as wordpress user
#
# Written by : Imane AMIRAT
# Created date: Dec 31, 2021
# Last modified: Dec 31, 2021
# Tested with : Python 3.9
# Script Revision: 0.1
#
##########################################################

# Import required python libraries

import os
import shutil
import errno
import time
import configparser
import tarfile
import tools
import argparse
import encrypt




# By Default, this script will read configuration from file /etc/backup-wp.conf
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
'''
Init :

Create the following folders :

/data/backup/dayJ
/data/backup/dayJ-1
/data/backup/dayJ-2
/data/backup/dayJ-3
/data/backup/dayJ-4
/data/backup/dayJ-5
/data/backup/dayJ-6


Before each new daily backup  :

1) Rotation :

rmdir /data/backup/day-J-6
mv /data/backup/day-J-5 to /data/backup/dayJ-6
mv /data/backup/day-J-4 to /data/backup/dayJ-5
mv /data/backup/day-J-3 to /data/backup/dayJ-4
mv /data/backup/day-J-2 to /data/backup/dayJ-3
mv /data/backup/day-J-1 to /data/backup/dayJ-2
mv /data/backup/day-J to /data/backup/dayJ-1
mkdir /data/backup/dayJ

2) Copy new backup files in local folder /data/backup/dayJ

3) Encrypt files

4) Remote folders rotation ie FTP

4) Copy files to remote location ie FTP
'''
# create parser
parser = argparse.ArgumentParser()

# add arguments to the parser
parser.add_argument("-v","--verbose",type=int,default=0,choices=[0,1,2],help="0 disable verbose, 1 minimal verbose, 2 debug mode")

# parse the arguments
args = parser.parse_args()

VERBOSE = args.verbose

CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

SMTP_HOST = config.get('SMTP','SMTP_HOST')
SMTP_FROM = config.get('SMTP','SMTP_FROM')
SMTP_TO = config.get('SMTP','SMTP_TO')

BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')
BACKUP_ROOT_PATH = config.get('BACKUP','LOCALBKPATH')

ENCRYPTION_KEYPATH = config.get('ENCRYPT','KEYPATH')


BACKUP_DEST = 'FTP'
FTP_SERVER = config.get('BACKUP','FTP_SERVER')
FTP_USER = config.get('BACKUP','FTP_USER')
FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
FTP_ROOT_PATH = config.get('BACKUP','FTP_PATH')


# Starting process
if VERBOSE >= 1:
    print("")
    print("Starting Wordpress backup process")

# Checking if local backup folders already exists or not. If not, we will create them.
if VERBOSE == 2:
        print("")
        print("Create local backup folders if not existing")
for index in range(int(BACKUP_RETENTION)):
    if index == 0:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
    else:
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
    try:
        os.stat(BACKUP_PATH)
    except:
        try:
            os.makedirs(BACKUP_PATH)
        except OSError as exc:
            if exc.errno == errno.EEXIST and os.path.isdir(BACKUP_PATH):
                pass

# Check if a backup already occured today
TODAY = time.strftime('%Y%m%d')

DATEFILE = BACKUP_ROOT_PATH + "/" + "DAYJ" + "/" + "date.txt"
try:
    os.stat(DATEFILE)
except:
    BACKUP_ROTATION = False
    if VERBOSE == 2:
        print("ROTATION = False ")
    pass
else:
    # First read content of datefile
    datefile = open(DATEFILE,"r")
    DATEINFILE = datefile.readline()
    # Now compare DATEINFILE with TODAY
    if DATEINFILE == TODAY:
        # Backup already occured today, so no ROTATION needed
        BACKUP_ROTATION = False
        if VERBOSE == 2:
            print("ROTATION = False ")
    else:
        # Local Backup Rotation
        BACKUP_ROTATION = True
        if VERBOSE == 2:
            print("")
            print("Local backup folders rotation")
            print("")
        # Delete DAYJ-RETENTION-1 folder
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ-" + str(int(BACKUP_RETENTION)-1)
        try:
            if VERBOSE == 2:
                print("Delete of " + BACKUP_PATH)
            shutil.rmtree(BACKUP_PATH, ignore_errors=False, onerror=None)
        except:
            if VERBOSE == 2:
                print("Error during delete of " + BACKUP_PATH)
            MESSAGE="""Backup failed
            Error during delete of """ + BACKUP_PATH
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress", smtphost=SMTP_HOST)
            exit(1)
        # Move content of DAYJ-N to DAYJ-(N+1)
        for index in range(int(BACKUP_RETENTION)-2,-1,-1):
            if index == 0:
                BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ"
                BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-1"
            else:
                BACKUP_PATH_FROM = BACKUP_ROOT_PATH + "/DAYJ-" + str(index)
                BACKUP_PATH_TO = BACKUP_ROOT_PATH + "/DAYJ-" + str(index+1)
            if VERBOSE == 2:
                print("Rename from " + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO)
            try:
                os.rename(BACKUP_PATH_FROM,BACKUP_PATH_TO)
            except:
                    if VERBOSE == 2:
                        print("Error during rename of " + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO)
                    MESSAGE="""Backup failed
                    Error during rename of """ + BACKUP_PATH_FROM + " to " + BACKUP_PATH_TO
                    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
                    exit(1)
        # Create DAYJ folder
        BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"
        if VERBOSE == 2:
                print("Create folder " + BACKUP_PATH )
        os.mkdir(BACKUP_PATH)

BACKUP_PATH = BACKUP_ROOT_PATH + "/DAYJ"

# Part1 : Database backup.
if VERBOSE >=1 :
    print ("")
    print ("Starting Backup of MySQL")

dumpcmd = "mysqldump -h " + DB_HOST + " " + DB_NAME + " > " + BACKUP_PATH + "/" + DB_NAME + ".sql"
try:
    os.system(dumpcmd)
except:
    if VERBOSE == 2:
        print("Error during mysqldump")
    MESSAGE="""Backup failed
    Error during mysqldump"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)

gzipcmd = "gzip -f " + BACKUP_PATH + "/" + DB_NAME + ".sql"
try:
    os.system(gzipcmd)
except:
    if VERBOSE == 2:
        print("Error during Gzip of mysqldump")
    MESSAGE="""Backup failed
    Error during Gzip of mysqldump"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)
localMysqlBackup=BACKUP_PATH + "/" + DB_NAME + ".sql.gz"

if VERBOSE == 2:
        print("Local MySQL dump copied in " + localMysqlBackup )

if VERBOSE >=1:
    print ("")
    print ("Backup of MySQL completed")

# Part2 : WP Site backup.

if VERBOSE >=1:
    print ("")
    print ("Starting backup of Wordpress Site folder")
# Declare filename
wp_archive = BACKUP_PATH + "/" + "wordpress.site.tar.gz"

# Open file in write mode
try:
    tar = tarfile.open(wp_archive,"w:gz")
    tar.add(WP_PATH)
    tar.close()
except:
    if VERBOSE == 2:
        print("Error during Tar GZ  of Wordpress site")
    MESSAGE="""Backup failed
    Error during Tar GZ of of Wordpress site"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)

if VERBOSE == 2:
        print("Local Wordpress site dump copied in " + wp_archive )

if VERBOSE >= 1:
    print ("")
    print ("Backup of  Wordpress Site folder completed")

# Part 3 : Put datefile in DAYJ
try:
    datefile = open(DATEFILE,"w")
    datefile.write(TODAY)
    datefile.close()
except:
    if VERBOSE == 2:
        print("Error during create of DATEFILE")
    MESSAGE="""Backup failed
    Error during create of DATEFILE"""
    tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
    exit(1)


# Part 4 : Encrypt using AES-256
fdKey = open(ENCRYPTION_KEYPATH,'rb')
ENCRYPTION_KEY = fdKey.read()
for file in [localMysqlBackup,wp_archive,DATEFILE]:
    file_name = os.path.basename(file)
    if VERBOSE == 2:
        print("Encrypt file " + file_name)
    try:
        encrypt.encrypt_file(file,ENCRYPTION_KEY)
    except:
        if VERBOSE == 2:
            print("Error during encryption of file " + file_name)
        MESSAGE="""Backup failed
        Error during encryption of file """ + file_name
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)

# Part 5 : Copy to BACKUP_DEST
if VERBOSE >= 1:
    print ("")
    print ("Starting Copy to FTP Server")
    print ("")

try:
    ftpserver=tools.connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
except:
    if VERBOSE == 2:
        print("Error during connection to FTP Server " + FTP_SERVER + " : please check parameters")
        MESSAGE="""Backup failed
        Error during connection to FTP Server """ + FTP_SERVER + " : please check parameters"
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)

try:
    ftpserver.cwd(FTP_ROOT_PATH)
except:
    if VERBOSE == 2:
        print("Error during CWD on FTP Server " + FTP_SERVER + " : please check parameters")
        MESSAGE="""Backup failed
        Error during CWD on FTP Server """ + FTP_SERVER + " : please check parameters"
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)

if VERBOSE == 2:
    print ("Init : Create FTP folder if not existing")

for index in range(int(BACKUP_RETENTION)):
    if index == 0:
        FTP_PATH = "DAYJ"
    else:
        FTP_PATH = "DAYJ-" + str(index)

    # First check if FTP_PATH already exists
    try:
        ftpserver.cwd(FTP_PATH)
    except:
        if VERBOSE == 2:
            print(FTP_PATH + " does not exists already")
            print("Create folder " + FTP_PATH)
        try:
            ftpserver.mkd(FTP_PATH)
        except:
            if VERBOSE == 2:
                print("Error during Create folder of " + BACKUP_PATH + " ie Folder already exist")
            MESSAGE="""Backup failed
            Error during create folder of """ + FTP_PATH + " ie Folder already exist"
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)
        else:
            if VERBOSE == 2:
                print(FTP_PATH + " created successfuly")
    else:
        if VERBOSE == 2:
            print(FTP_PATH + " already exists")
        ftpserver.cwd("..")

if BACKUP_ROTATION == True:
    # Backup Rotation
    if VERBOSE == 2:
        print("")
        print ("FTP folders rotation")
    # Delete DAYJ-RETENTION-1 folder
    FTP_PATH="DAYJ-" + str(int(BACKUP_RETENTION)-1)
    if VERBOSE == 2:
        print("")
        print("First delete all files in " + FTP_PATH)
    try:
        ftpserver.cwd(FTP_PATH)
    except:
        if VERBOSE == 2:
            print("Error accessing folder " + FTP_PATH + " ie Folder does not exist")
        MESSAGE="""Backup failed
        Error accessing folder """ + FTP_PATH + " ie Folder does not exist"
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)
    try:
        file_list = ftpserver.nlst()
    except:
        if VERBOSE == 2:
            print("Error listing files in folder " + FTP_PATH )
        MESSAGE="""Backup failed
        Error listing files in folder """ + FTP_PATH
        tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
        exit(1)
    for file in ftpserver.nlst():
        if VERBOSE == 2:
            print("Delete file " + file)
        ftpserver.delete(file)
    ftpserver.cwd("..")
    try:
        if VERBOSE == 2:
            print("Delete folder " + FTP_PATH)
        ftpserver.rmd(FTP_PATH)
    except:
        if VERBOSE == 2:
            print("Error during delete of folder " + FTP_PATH + " ie Folder not empty")
            MESSAGE="""Backup failed
            Error during delete of folder """ + FTP_PATH + " ie Folder not empty"
            tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
            exit(1)
    if VERBOSE == 2:
        print("")
    # Move content of DAYJ-N to DAYJ-(N+1)
    for index in range(int(BACKUP_RETENTION)-2,-1,-1):
        if index == 0:
            FTP_PATH_FROM = "DAYJ"
            FTP_PATH_TO = "DAYJ-1"
        else:
            FTP_PATH_FROM = "DAYJ-" + str(index)
            FTP_PATH_TO = "DAYJ-" + str(index+1)
        if VERBOSE == 2:
            print("Rename from " + FTP_PATH_FROM + " to " + FTP_PATH_TO)
        ftpserver.rename(FTP_PATH_FROM,FTP_PATH_TO)
    # Create DAYJ folder
    FTP_PATH="DAYJ"
    if VERBOSE == 2:
            print("")
            print("Create folder " + FTP_PATH)
            print("")
    ftpserver.mkd(FTP_PATH)

FTP_PATH="DAYJ"
for file in [localMysqlBackup + ".bin",wp_archive + ".bin",DATEFILE + ".bin"]:
    if VERBOSE >= 1:
        print("Transfering " + file + " to " + FTP_PATH)
    result=tools.uploadftp(ftpserver,file,FTP_PATH)

tools.closeftp(ftpserver)

if VERBOSE >= 1:
    print ("")
    print ("Copy to FTP Server completed")



if VERBOSE >= 1:
    print ("")
    print ("Backup script completed")
    print ("Your backups have also been created locally in " + BACKUP_PATH + " directory")

MESSAGE="""Backup script completed
Your backups have also been created locally in """ + BACKUP_PATH + " directory"

tools.sendmail(mailfrom=SMTP_FROM,mailto=SMTP_TO,message=MESSAGE,subject="Backup of Wordpress of " + TODAY, smtphost=SMTP_HOST)
