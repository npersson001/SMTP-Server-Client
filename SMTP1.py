#!/usr/bin/env python
import sys
import socket
import errno

#save all the properly formatted mail into a mailbox
def forwardMail():
    for recipient in recipients:
        fileLocation = "./forward/%s" % recipient.split("@")[1].rstrip()
        file = open(fileLocation, "a")
        file.write(message)
        file.close()

#add sender to the message
def addSender(string, start, finish):
    global sender
    sender.append(string[start:finish])

#add recipients to the recipient list
def addRecipient(string, start, finish):
    global recipients
    recipients.append(string[start:finish])

#create the message
def createMessage():
    global message, messageBody
    message += "From: <%s>\n" % sender[0]
    for recipient in recipients:
        message += "To: <%s>\n" % recipient
    #messageBody = messageBody[:-2]
    message += messageBody
    forwardMail()

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
    if(current_pos >= len(string)):
        return current_pos
    if(string[current_pos] != '\n'):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    return current_pos

#check for the end of line character without printing an error message
def checkCRLF(string, current_pos):
    if (current_pos >= len(string)):
        return current_pos
    if(string[current_pos] != '\n'):
        return 0
    return current_pos

#check that first char is letter and then consecutive chars are as well
def parseName(string, current_pos):
    if(string[current_pos].isalpha() == False):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    current_pos += 1
    if(string[current_pos].isalnum() == False or current_pos >= len(string)):
        connection.send("501 Syntax error in parameters or arguments")
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
        connection.send("501 Syntax error in parameters or arguments")
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
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    current_pos += 1
    if (parseDomain(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseDomain(string, current_pos)
    return current_pos

#checks for "<" and passes path and checks ">"
def parsePath(string, current_pos):
    if (string[current_pos] != '<'):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    current_pos += 1
    if (parseMailbox(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseMailbox(string, current_pos)
    if (string[current_pos] != '>'):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    current_pos += 1
    return current_pos

#used for the MAIL FROM: command for the path
def parseReversePath(string, current_pos):
    if(parsePath(string, current_pos) == 0):
        return 0
    else:
        startSender = current_pos + 1
        finishSender = parsePath(string, current_pos) - 1
        addSender(string, startSender, finishSender)
        return parsePath(string, current_pos)

#used for the RCPT TO: command for the path
def parseForwardPath(string, current_pos):
    global recipients
    if(parsePath(string, current_pos) == 0):
        return 0
    else:
        startRecipient = current_pos + 1
        finishRecipient = parsePath(string, current_pos) - 1
        if(string[startRecipient:finishRecipient] not in recipients):
            addRecipient(string, startRecipient, finishRecipient)
        return parsePath(string, current_pos)

#checks for no spaces or any number of spaces
def parseNullspace(string, current_pos):
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#checks for at least one space
def parseWhitespace(string, current_pos):
    if(current_pos >= len(string)):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    if (string[current_pos] != ' ' and string[current_pos] != '\t'):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#checks for "MAIL"<SP>^+"FROM:"<SP>^* then parses reverse-path then <SP>^* and
#<CRLF>
def parseMailFromCmd(string, current_pos):
    global waitingForMail, waitingForRcpt
    if (string[:4] != "MAIL"):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    current_pos += 4
    if (parseWhitespace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseWhitespace(string, current_pos)
    if (string[current_pos:current_pos + 5] != "FROM:"):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    current_pos += 5
    if (current_pos >= len(string)):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    if (parseNullspace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseNullspace(string, current_pos)
    if (parseReversePath(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseReversePath(string, current_pos)
    if (parseNullspace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseNullspace(string, current_pos)
    if(parseCRLF(string, current_pos) == 0):
        return 0
    connection.send("250 OK")
    waitingForRcpt = True
    waitingForMail = False

#checks for "RCPT"<SP>^+"TO:"<SP>^* then parses forward-path then <SP>^* and
#<CRLF>
def parseRcptToCmd(string, current_pos):
    global waitingForData
    if (string[:4] != "RCPT"):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    current_pos += 4
    if (parseWhitespace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseWhitespace(string, current_pos)
    if (string[current_pos:current_pos + 3] != "TO:"):
        connection.send("500 Syntax error: command unrecognized")
        return 0
    current_pos += 3
    if (current_pos >= len(string)):
        connection.send("501 Syntax error in parameters or arguments")
        return 0
    if (parseNullspace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseNullspace(string, current_pos)
    if (parseForwardPath(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseForwardPath(string, current_pos)
    if (parseNullspace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseNullspace(string, current_pos)
    if(parseCRLF(string, current_pos) == 0):
        return 0
    connection.send("250 OK")
    waitingForData = True

#checks "DATA"<SP>^*<CRLF>
def parseDataCmd(string, current_pos):
    global waitingForData, waitingForDataBlock, waitingForMail, message
    if(waitingForDataBlock == False):
        if (string[:4] != "DATA"):
            connection.send("500 Syntax error: command unrecognized")
            return 0
        current_pos += 4
        if (parseNullspace(string, current_pos) == 0):
            return 0
        else:
            current_pos = parseNullspace(string, current_pos)
        if(parseCRLF(string, current_pos) == 0):
            return 0
        connection.send("354 Start mail input; end with <CRLF>.<CRLF>")
        waitingForDataBlock = True
        waitingForData = False
    else:
        if(string[0] == '.'):
            current_pos += 1
            if (checkCRLF(string, current_pos) == 1):
                connection.send("250 OK")
                createMessage()
                resetState()

#checks for at least one space without printing an error message
def checkWhitespace(string, current_pos):
    if(current_pos >= len(string)):
        return 0
    if (string[current_pos] != ' ' and string[current_pos] != '\t'):
        return 0
    for i in range(current_pos, len(string)):
        if (string[i] != ' ' and string[i] != '\t'):
            return i
    return current_pos

#check if the Mail command is correct
def checkMail(string, current_pos):
    if (string[:4] != "MAIL"):
        return 0
    current_pos += 4
    if (checkWhitespace(string, current_pos) == 0):
        return 0
    else:
        current_pos = checkWhitespace(string, current_pos)
    if (string[current_pos:current_pos + 5] != "FROM:"):
        return 0
    return current_pos

#check if the RCPT command is correct
def checkRCPT(string, current_pos):
    if (string[:4] != "RCPT"):
        return 0
    current_pos += 4
    if (checkWhitespace(string, current_pos) == 0):
        return 0
    else:
        current_pos = checkWhitespace(string, current_pos)
    if (string[current_pos:current_pos + 3] != "TO:"):
        return 0
    return current_pos

#check if the data command is correct
def checkData(string, current_pos):
    if (string[:4] != "DATA"):
            return 0
    current_pos += 4
    if (parseNullspace(string, current_pos) == 0):
        return 0
    else:
        current_pos = parseNullspace(string, current_pos)
    if(checkCRLF(string, current_pos) == 0):
        return 0
    return current_pos

#prints the "ok" message if the string passes the parsing, passes to parser
#uses states to decide which command to wait for
def parse(string):
    global waitingForMail, waitingForRcpt, waitingForData, waitingForDataBlock
    if(string[0] == 'M' and waitingForDataBlock == False):
        if(checkMail(string, 0) == 0):
            connection.send("500 Syntax error: command unrecognized")
            return 0
        if(waitingForMail == False):
            connection.send("503 Bad sequence of commands")
            resetState()
            return 0
        parseMailFromCmd(string, 0)
    elif(string[0] == 'R' and waitingForDataBlock == False):
        if(checkRCPT(string, 0) == 0):
            connection.send("500 Syntax error: command unrecognized")
            return 0
        if (waitingForRcpt == False):
            connection.send("503 Bad sequence of commands")
            resetState()
            return 0
        parseRcptToCmd(string, 0)
    elif(string[0] == 'D' and waitingForDataBlock == False):
        if(checkData(string, 0) == 0):
            connection.send("500 Syntax error: command unrecognized")
            return 0
        waitingForRcpt = False
        if (waitingForData == False):
            connection.send("503 Bad sequence of commands")
            resetState()
            return 0
        parseDataCmd(string, 0)
    elif(waitingForDataBlock == True):
        parseDataCmd(string,0)
    else:
        connection.send("500 Syntax error: command unrecognized")

#check that there is an argv[1]
if len(sys.argv) <= 1:
    sys.exit()

#globals declared to determine order of incomming commands
waitingForMail = True
waitingForRcpt = False
waitingForData = False
waitingForDataBlock = False
message = ""
messageBody = ""
recipients = []
sender = []

#use a try catch so that any errors encountered will be caught well
try:
    #sets up listening socket
    serversocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    serversocket.bind((socket.gethostname(), int(sys.argv[1])))
    serversocket.listen(5)
    while True:
        #do the handshaking process
        connection, address = serversocket.accept()
        mes = "220 " + socket.gethostname()
        connection.send(mes)
        connected = True
        while connected:
            buf = connection.recv(1024)
            if len(buf) > 0:
                bufArray = buf.split(" ")
                if len(bufArray) >= 2:
                    code = bufArray[0].rstrip()
                    messageRec = bufArray[1].rstrip()
                    if code == "HELO":
                        mes = "250 " + messageRec + " pleased to meet you"
                        connection.send(mes)
                        #start loop for parsing
                        while True:
                            buf = connection.recv(1024)
                            bufArray = buf.split("\n")
                            if(bufArray[-1] == ""):
                                bufArray = bufArray[0:-1]
                            if(buf == "QUIT"):
                                resetState()
                                connected = False
                                connection.close()
                                break
                            if (waitingForDataBlock == True):
                                for i in xrange(0, len(bufArray)):
                                    if(bufArray[i] != "."):
                                        messageBody += bufArray[i] + "\n"
                                    parse(bufArray[i] + "\n")
                            else:
                                parse(buf)
except socket.error as err:
    if err.errno == errno.ECONNREFUSED:
        sys.stdout.write("connection refused\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.ECONNABORTED:
        sys.stdout.write("connection aborted\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EREMOTEIO:
        sys.stdout.write("error reading and writing remotely\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.ENXIO:
        sys.stdout.write("address/device does not exist\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EPERM:
        sys.stdout.write("operation is not permitted\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EACCES:
        sys.stdout.write("access denied\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EFAULT:
        sys.stdout.write("bad address\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EPIPE:
        sys.stdout.write("broken pipe\n")
        connection.close()
        sys.exit()
    elif err.errno == errno.EIO:
        sys.stdout.write("I/O error encountered\n")
        connection.close()
        sys.exit()
    else:
        sys.stdout.write("socket error encountered\n")
        connection.close()
        sys.exit()