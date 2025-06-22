import socket
import random

#用于存储服务器返回的反转后的消息
messageReversed = ""

with open("message.txt", 'rb') as file:
    messageAll = file.read()
    messageSize = len(messageAll)
    minL = int(input("请输入数据传输的最小长度："))
    maxL = int(input("请输入数据传输的最大长度："))

    lengthList = [] #存储每个数据段的长度
    tempSize = messageSize #临时变量，用于跟踪剩余未发送的数据大小
    temp = 0

    #循环随机生成每个数据段的长度
    while  tempSize > 0:
        if tempSize <= minL: #如果剩余数据小于等于最小长度，则将剩余数据加到前一个段的长度上
            lengthList[temp-1] += tempSize
            break

        maxL = min(tempSize, maxL) #确保当前段的最大长度不超过剩余数据大小
        length = random.randrange(minL, maxL) #随机生成当前数据段的长度
        tempSize -= length
        lengthList.append(length)
        temp += 1

    N = len(lengthList)

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as clientSocket:
        serverIP = input("请输入服务端IP：")
        serverPort = int(input("请输入服务端端口号："))
        clientSocket.connect((serverIP, serverPort))

        # 发送初始化信息：类型b'00' + 数据段总数量N（4字节大端模式）
        clientSocket.send(b'00' + N.to_bytes(4, 'big'))
        dataSent = 0 #已发送的数据量
        lengthNum = 0 #当前正在处理的数据段索引

        data = clientSocket.recv(1024)
        if data[0:2] != b'01': #如果服务器响应的类型不是b'01'，表示服务器未响应
            print("服务器未响应！")
            clientSocket.close()
        else:
            #构造并发送第一个数据段：类型b'10' + 当前数据段长度 + 数据内容
            answer = b'10' + lengthList[lengthNum].to_bytes(4, 'big') + messageAll[dataSent: dataSent + lengthList[lengthNum]]
            dataSent += lengthList[lengthNum]
            clientSocket.send(answer)
        while True:
            data = clientSocket.recv(1024)
            type = data[0:2]
            if type == b'11': #如果数据类型是b'11'，表示是服务器返回的反转数据
                length = int.from_bytes(data[2:6], 'big')
                #打印当前数据段的序号和反转后的内容
                print(f"{lengthNum+1}:{data[6:6+length].decode()}")
                #将反转后的数据段添加到 messageReversed 的最前面以实现整体反转
                messageReversed = data[6:6+length].decode() + messageReversed[0:]
                #构造并发送下一个数据段
                answer = b'10' + lengthList[lengthNum].to_bytes(4, 'big') + messageAll[dataSent:dataSent + lengthList[lengthNum]]
                dataSent += lengthList[lengthNum]
                clientSocket.send(answer)
                lengthNum += 1

                # 如果所有数据段都已处理完毕则关闭套接字
                if lengthNum == N:
                    clientSocket.close()
                    break

with open("messageReturn.txt", 'w') as file:
    file.write(messageReversed)
