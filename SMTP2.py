#/usr/bin/env python
import sys
import socket
import errno

#all previous code for parsing (note: all will not be used)
#reset all the global variables for the state of the server
def resetState():
    global waitingForMail, waitingForRcpt, waitingForData, waitingForDataBlock, recipients, message, messageBody, sender
    waitingForMail = True
    waitingForRcpt = False
    waitingForData = False
    waitingForDataBlock = False
    sender = []
    recipients = []
    message = ""
    messageBody = ""

#check for the end of line character
def parseCRLF(string, current_pos):
    if (current_pos >= len(string)):
        return 0
    if(string[current_pos] != '\n'):
        sys.stdout.write("expected CRLF not found\n")
        return 0
    return current_pos

#check for the end of line character without error message
def checkCRLF(string, current_pos):
    if (current_pos >= len(string)):
        return 0
    if(string[current_pos] != '\n'):
        return 0
    return current_pos

#check that first char is letter and then consecutive chars are as well
def parseName(string, current_pos):
    if(string[current_pos].isalpha() == False):
        sys.stdout.write("first character in name not a letter\n")
        return 0
    current_pos += 1
    if(string[current_pos].isalnum() == False or current_pos >= len(string)):
        sys.stdout.write("character other than number or letter found in name\n")
        return 0
    for i in range(current_pos, len(string)):
        if (string[i].isalnum() == False):
            return i
    return current_pos

#passes the element to name in the grammar, useless for now
def parseElement(string, current_pos):
    return parseName(string, current_pos)

#checks first char is ascii and not special, then checks rest of chars for same
def parseString(string, current_pos):
    special_char = ['<','>','(',')','[',']','\\','.',',',';',':','@','"',' ']
    if (ord(string[current_pos]) >= 128 or string[current_pos] in special_char or string[current_pos] == '\n'):
        sys.stdout.write("invalid special character found\n")
        return 0
    for i in range(current_pos, len(string)):
        if (ord(string[i]) >= 128 or string[i] in special_char):
            return i
    return current_pos

#passes elements to parseElement and checks for unlimited "." and elements
def parseDomain(string, current_pos):
    if (parseElement(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseElement(string, current_pos)
    while (True):
        if (string[current_pos] == '.'):
            current_pos += 1
            if (parseElement(string, current_pos) == 0):
                return 0
            else:
                current_pos = parseElement(string, current_pos)
        else:
            return current_pos
    return current_pos

#useless for now, from local-part to string in grammar
def parseLocalPart(string, current_pos):
    return parseString(string, current_pos)

#passes along local-part followed by "@" followed by domain
def parseMailbox(string, current_pos):
    if (parseLocalPart(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseLocalPart(string, current_pos)
    if (string[current_pos] != '@'):
        sys.stdout.write("expected @ not found\n")
        return 0
    current_pos += 1
    if (parseDomain(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseDomain(string, current_pos)
    return current_pos

#checks for no spaces or any number of spaces
def parseNullspace(string, current_pos):
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#checks for at least one space
def parseWhitespace(string, current_pos):
    if(current_pos >= len(string)):
        sys.stdout.write("current_pos out of bounds when searching for whitespace\n")
        return 0
    if (string[current_pos] != ' ' and string[current_pos] != '\t'):
        sys.stdout.write("no whitespace found\n")
        return 0
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#checks for at least one space without sys.stdout.write(ing an error message
def checkWhitespace(string, current_pos):
    if(current_pos >= len(string)):
        return 0
    if (string[current_pos] != ' ' and string[current_pos] != '\t'):
        return 0
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#states for the client reading forward file
waitingFrom = True
waitingTo = False
waitingData = False
sender = []
recipients = []
subject = ""
message = []

#check for number of arguments
if len(sys.argv) <= 2:
    sys.stdout.write("hostname and port required\n")
    sys.exit()

#take input from the user
try:
    #get from part of message
    while True:
        userInput = raw_input("From: \n")
        if parseMailbox(userInput.rstrip(), 0) != 0:
            sender.append(userInput.rstrip())
            break
    #get to part of message
    toCorrect = False
    while True:
        userInput = raw_input("To: \n")
        rcptArray = userInput.split(",")
        for rcpt in rcptArray:
            if parseMailbox(rcpt.lstrip().rstrip(), 0) != 0:
                recipients.append(rcpt.lstrip().rstrip())
                toCorrect = True
            else:
                recipients = []
                toCorrect = False
                break
        if toCorrect:
            break
    #get subject part of message
    userInput = raw_input("Subject: \n")
    subject += userInput.rstrip()
    #get the body of the message
    gettingFirstMessage = True
    while True:
        if gettingFirstMessage:
            userInput = raw_input("Message: \n")
            gettingFirstMessage = False
            if userInput == ".":
                doneGettingMessage = True
                break
            else:
                message.append(userInput.rstrip())
        else:
            userInput = raw_input()
            if userInput == ".":
                doneGettingMessage = True
                break
            else:
                message.append(userInput.rstrip())
except EOFError:
    sys.stdout.write("EOF reached during data collection\n")
    sys.exit()

#make sure to give error if we dont get input for each one
if len(sender) != 1:
    sys.stdout.write("invalid number of senders\n")
    sys.exit()
if len(recipients) < 1:
    sys.stdout.write("invalid number of recipients\n")
    sys.exit()
if subject == "":
    sys.stdout.write("no subject line provided\n")
    sys.exit()
if doneGettingMessage == False:
    sys.stdout.write("no message provided\n")
    sys.exit()

#create messages to send
mailFrom = "MAIL FROM: <" + sender[0].rstrip() + ">"
mailTo = []
for rec in recipients:
    mailTo.append("RCPT TO: <" + rec.rstrip() + ">")
mailData = "DATA"
mailMessage = []
mailMessage.append("From: <" + sender[0].rstrip() + ">")
for rec in recipients:
    mailMessage.append("To: <" + rec + ">")
mailMessage.append("Subject: " + subject)
mailMessage.append("")
for mes in message:
    mailMessage.append(mes)
mailMessage.append(".")
mailQuit = "QUIT"
tempMail = []
for mes in mailMessage:
    tempMail.append(mes + "\n")
mailMessage = tempMail

#in a try catch so errors are properly handled
try:
    #connect to server and get to point where the message can be sent
    clientsocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    clientsocket.connect((sys.argv[1], int(sys.argv[2])))
    buf = clientsocket.recv(1024)
    if len(buf) > 0:
        buf = buf.split(" ")[0]
        if buf != "220":
            sys.stdout.write("invalid 220 message received\n")
            clientsocket.close()
            sys.exit()
    mes = "HELO " + socket.gethostname()
    clientsocket.send(mes)
    buf = clientsocket.recv(1024)
    if len(buf) > 0:
        buf = buf.split(" ")[0]
        if buf != "250":
            sys.stdout.write("invalid HELO message received\n")
            clientsocket.close()
            sys.exit()

    #send messages that were created
    clientsocket.send(mailFrom)
    buf = clientsocket.recv(1024)
    if len(buf) > 0:
        buf = buf.split(" ")[0]
        if buf != "250":
            sys.stdout.write("invalid MAIL FROM message received\n")
            clientsocket.close()
            sys.exit()
    for rec in mailTo:
        clientsocket.send(rec)
        buf = clientsocket.recv(1024)
        if len(buf) > 0:
            buf = buf.split(" ")[0]
            if buf != "250":
                sys.stdout.write("invalid RCPT TO message received\n")
                clientsocket.close()
                sys.exit()
    clientsocket.send(mailData)
    buf = clientsocket.recv(1024)
    if len(buf) > 0:
        buf = buf.split(" ")[0]
        if buf != "354":
            sys.stdout.write("invalid DATA message received\n")
            clientsocket.close()
            sys.exit()
    for mes in mailMessage:
        clientsocket.send(mes)
    buf = clientsocket.recv(1024)
    if len(buf) > 0:
        buf = buf.split(" ")[0]
        if buf != "250":
            sys.stdout.write("invalid end of DATA message received\n")
            clientsocket.close()
            sys.exit()
    clientsocket.send(mailQuit)
    #sys.stdout.write("closing the socket\n")
    clientsocket.close()
except socket.error as err:
    if err.errno == errno.ECONNREFUSED:
        sys.stdout.write("connection refused\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.ECONNABORTED:
        sys.stdout.write("connection aborted\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EREMOTEIO:
        sys.stdout.write("error reading and writing remotely\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.ENXIO:
        sys.stdout.write("address/device does not exist\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EPERM:
        sys.stdout.write("operation is not permitted\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EACCES:
        sys.stdout.write("access denied\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EFAULT:
        sys.stdout.write("bad address\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EPIPE:
        sys.stdout.write("broken pipe\n")
        clientsocket.close()
        sys.exit()
    elif err.errno == errno.EIO:
        sys.stdout.write("I/O error encountered\n")
        clientsocket.close()
        sys.exit()
    else:
        sys.stdout.write("socket error encountered\n")
        clientsocket.close()
        sys.exit()