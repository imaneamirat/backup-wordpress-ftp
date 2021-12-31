#!/usr/bin/python3

###########################################################
#
# This python script is used to restore Wordpress website and associated mysql database
# using mysql and tar utility.
# Backups are downloaded from either :
# - AWS S3 and encrypted using a private AES-256 key
# or
# - FTP server
#
# This scripts needs root privileges
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
import time
import pipes
import configparser
import tarfile
import tools
import argparse
import encrypt


# By Default, this script will read configuration from file /etc/backup-wp.conf
#
# Todo : Add the option -f to read parameters from a specified filename in the command line parameter
'''
1) Copy files from remote location ie FTP or S3 to /data/backup/RESTORE-DATE
2) Decrypt files
3) Import SQL backup in MySQL
4) Untar Site backup
'''
CONFIG_FILE = "/etc/backup-wp.conf"

config = configparser.ConfigParser()
config.read(CONFIG_FILE)

WP_PATH = config.get('WP','WP_PATH')
DB_HOST = config.get('DB','DB_HOST')
DB_NAME = config.get('DB','DB_NAME')

SMTP_HOST = config.get('SMTP','SMTP_HOST')
SMTP_FROM = config.get('SMTP','SMTP_FROM')
SMTP_TO = config.get('SMTP','SMTP_TO')

BACKUP_PATH = config.get('BACKUP','LOCALBKPATH')
BACKUP_RETENTION = config.get('BACKUP','BACKUP_RETENTION')

ENCRYPTION_KEYPATH = config.get('ENCRYPT','KEYPATH')

# create parser
parser = argparse.ArgumentParser()

# add arguments to the parser
parser.add_argument("-d","--day",type=int,default=0,help="index of day in the past to be restored. Possible value from 0 to BACKUP_RETENTION - 1")
parser.add_argument("-l","--local",action='store_true', help="Restore from local backup folders only")
parser.add_argument("-v","--verbose",type=int,default=0,choices=[0,1,2],help="0 disable verbose, 1 minimal verbose, 2 debug mode")

# parse the arguments
args = parser.parse_args()

DAYTORESTORE=args.day
VERBOSE = args.verbose
LOCALRESTORE = args.local

if LOCALRESTORE:
    BACKUP_DEST = 'LOCAL'
else:
    BACKUP_DEST = 'FTP'

if BACKUP_DEST == 'FTP':
    FTP_SERVER = config.get('BACKUP','FTP_SERVER')
    FTP_USER = config.get('BACKUP','FTP_USER')
    FTP_PASSWD = config.get('BACKUP','FTP_PASSWD')
    FTP_PATH = config.get('BACKUP','FTP_PATH')
else: # BACKUP_DEST == 'LOCAL' ''
    pass


if BACKUP_DEST == 'LOCAL':
    if DAYTORESTORE:
        TODAYRESTOREPATH = BACKUP_PATH + '/' + "DAYJ-" + str(DAYTORESTORE)
    else:
        TODAYRESTOREPATH = BACKUP_PATH + '/' + "DAYJ"

else:
    # Getting current DateTime to create the separate backup folder like "20210921".

    DATETIME = time.strftime('%Y%m%d')
    TODAYRESTOREPATH = BACKUP_PATH + '/' + "RESTORE-" +DATETIME


    # Checking if backup folder already exists or not. If not exists will create it.
    try:
        os.stat(TODAYRESTOREPATH)
    except:
        os.mkdir(TODAYRESTOREPATH)




# Part1 : Retrieve backup files

MysqlBackupFilename="wordpress.sql.gz.bin"
WordPressBackupFilename="wordpress.site.tar.gz.bin"

if BACKUP_DEST == 'FTP':
    print ("")
    print ("Starting Download from FTP Server")

    if DAYTORESTORE == 0:
        RESTORE_FOLDER = "DAYJ"
    else:
        RESTORE_FOLDER = "DAYJ-" + str(DAYTORESTORE)
    ftpserver=tools.connectftp(FTP_SERVER,FTP_USER,FTP_PASSWD)
    ftpserver.cwd(FTP_PATH + "/" + RESTORE_FOLDER)

    for file in [MysqlBackupFilename,WordPressBackupFilename]:
        print("Transfering" + file)
        result=tools.downloadftp(ftpserver,file,TODAYRESTOREPATH)

    tools.closeftp(ftpserver)

    print ("")
    print ("Copy from FTP Server completed")


# Part 2 : Decrypt files
fdKey = open(ENCRYPTION_KEYPATH,'rb')
ENCRYPTION_KEY = fdKey.read()

for file in [MysqlBackupFilename,WordPressBackupFilename]:
    print("Decrypting " + file)
    result=encrypt.decrypt_file(TODAYRESTOREPATH + "/" + file,ENCRYPTION_KEY)

# Part3 : Database Restore.
print ("")
print ("Starting Import of MySQL Dump")

importcmd = "zcat " + pipes.quote(TODAYRESTOREPATH) + "/" + DB_NAME + ".sql.gz | mysql -h " + DB_HOST + " " + DB_NAME

os.system(importcmd)


print ("")
print ("Dump of MySQL imported")

# Part3 : WP Site Restore.

print ("")
print ("Starting Restore of Wordpress Site folder")
#declare filename
wp_archive= TODAYRESTOREPATH + "/" + "wordpress.site.tar.gz"

#open file in read mode
tar = tarfile.open(wp_archive,"r:gz")
tar.extractall("/")
tar.close()

print ("")
print ("Restore of  Wordpress Site folder completed")


print ("")
print ("Restore script completed")

