import socket
import threading

#服务器IP与PORT
serverIP = "127.0.0.1"
serverPort = 8080


def handel (clientSocket, clisentAddress):
    reN = 0
    while True:
        # 初始化接收消息的段数
        dataRaw = clientSocket.recv(1024)
        type = dataRaw[0:2]

        #如果数据类型是 b'00'，表示客户端正在发送初始化信息（消息段数N）
        if type == b'00':
            reN = int.from_bytes(dataRaw[2:6], 'big')
            answer = b'01'
            clientSocket.send(answer)

        #如果数据类型是 b'10'，表示客户端正在发送数据段
        if type == b'10':
            while reN > 0:
                #从字节中解析出当前数据段的长度
                length = int.from_bytes(dataRaw[2:6], 'big')
                #提取实际数据部分并反转
                dataReversed = dataRaw[6:]
                dataReversed = dataReversed[::-1]
                answer = b'11' + length.to_bytes(4, 'big') + dataReversed
                clientSocket.send(answer)
                reN -= 1
                #接收下一段数据
                dataRaw = clientSocket.recv(1024)
            clientSocket.close()
            return


with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as serverSocket:
    serverSocket.bind((serverIP,serverPort))
    serverSocket.listen(10)
    print(f"服务端已在IP:{serverIP},端口号{serverPort}上监听")
    while True:
        clientSocket, clientAddress = serverSocket.accept()
        print(f"客户(IP:{clientAddress})已连接至服务")
        #为每个客户端连接创建一个新的线程来处理
        clientThread = threading.Thread(target=handel,args=(clientSocket,clientAddress))
        clientThread.run()