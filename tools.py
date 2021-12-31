import os
import ftplib
import smtplib
from email.message import EmailMessage
from Crypto.Random import get_random_bytes


def sendmail(mailfrom="address@example.com",mailto="imaneamirat08@gmail.com",message="",subject="",smtphost="localhost"):
    # me == the sender's email address
    # you == the recipient's email address
    # Create a text/plain message
    msg = EmailMessage()
    msg['Subject'] = subject
    msg['From'] = mailfrom
    msg['To'] = mailto
    msg.set_content(message)

    # Send the message via our own SMTP server.
    s = smtplib.SMTP(smtphost)
    s.send_message(msg)
    s.quit()

def connectftp(ftpserver = "172.16.30.32" , username = 'anonymous', password = 'anonymous@', passive = False):
    """connect to ftp server and open a session
       - ftpserver: IP address of the ftp server
       - username: login of the ftp user ('anonymous' by défaut)
       - password: password of the ftp user ('anonymous@' by défaut)
       - passive: activate or disable ftp passive mode (False par défaut)
       return the object 'ftplib.FTP' after connection and opening of a session
    """
    ftp = ftplib.FTP_TLS()
    ftp.connect(ftpserver)
    ftp.login(username, password)
    ftp.set_pasv(passive)
    ftp.prot_p()
    return ftp

def uploadftp(ftp, ficdsk,ftpPath):
    '''
    Upload the file ficdsk from local folder to the current ftp folder
        - ftp: object 'ftplib.FTP' on an open session
        - ficdsk: local name of the file to upload
        - ficPath: FTP path where to store the file
    '''
    repdsk, ficdsk2 = os.path.split(ficdsk)
    ficftp = ftpPath + "/" + ficdsk2
    with open(ficdsk, "rb") as f:
        ftp.storbinary("STOR " + ficftp, f)

def downloadftp(ftp, ficftp, repdsk='.', ficdsk=None):
    """Download the file ficftp from ftpserver and put it in the local folder repdsk
       - ftp: object 'ftplib.FTP' from an open session
       - ficftp: name of the file to download
       - repdsk: local folder where you want to store the file
       - ficdsk: optional, if you want to rename the file locally
    """
    if ficdsk==None:
        ficdsk=ficftp
    with open(os.path.join(repdsk, ficdsk), 'wb') as f:
        ftp.retrbinary('RETR ' + ficftp, f.write)

def closeftp(ftp):
    """Close FTP connection
       - ftp: variable 'ftplib.FTP' on open connection
    """
    try:
        ftp.quit()
    except:
        ftp.close()