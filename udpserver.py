from datetime import datetime
import socketserver
import struct
import random


#服务器IP与PORT
serverIP = "127.0.0.1"
serverPort = 8080

#服务器模拟丢包率
dropRate = 0.5

#UDP报文头部结构
headerFormat = "!BIIHH"
headerLength = struct.calcsize(headerFormat)

#报文类型
syn = 0x00
synAck = 0x01
dataFlow = 0x02 #数据包
dataAck = 0x03
fin = 0x04
finAck = 0x05


class Packet:
    """
    将Packet对象打包成字节串，用于传输。
    头部组成: type(1B) + seq(4B) + ack(4B) + window(2B) + dataLength(2B) + data
    """
    def __init__(self, type=0x00, seq=0, ack=0, window=0, data=b''):
        self.type = type
        self.seq = seq
        self.ack = ack
        self.window = window
        self.dataLength = len(data)
        self.data = data

    def pack(self):
        return struct.pack(headerFormat, self.type, self.seq, self.ack, self.window, self.dataLength) + self.data

    def unpack(self, rawBytes):
        packetData = rawBytes[:headerLength]
        self.data = rawBytes[headerLength:]
        # 解包头部
        (
            self.type,
            self.seq,
            self.ack,
            self.window,
            self.dataLength,
        ) = struct.unpack(headerFormat, packetData)

class clientHandeler (socketserver.BaseRequestHandler):
    def handle(self):
        data = self.request[0]
        clientAddress = self.client_address
        clientSocket = self.request[1]
        curTime = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        rawPack = Packet()
        try:
            rawPack.unpack(data)
        except ValueError as e:
            print(f"[{curTime}] 错误:收到来自{clientAddress}的无效报文: {e}")
            return

        #判断并处理syn请求
        if rawPack.type == syn:
            print(f"[{curTime}] 收到来自{clientAddress}的syn请求")
            synAckPack = Packet(type=synAck, seq=0, ack=rawPack.seq + 1, window=400)
            clientSocket.sendto(synAckPack.pack(), clientAddress)
            print(f"--->[{curTime}] 发送synAck报文给{clientAddress}")

        #处理dataFlow请求
        elif rawPack.type == dataFlow:
            #模拟随机丢包
            if (random.random() < dropRate):
                print(f"[{curTime}] 丢弃来自{clientAddress}的 seq:{rawPack.seq} 的数据报文")
                return
            print(f"[{curTime}] 收到来自{clientAddress}的 seq:{rawPack.seq} dataFlow报文")
            #确认号=收到的包的序列号+数据长度
            newAck = rawPack.seq + rawPack.dataLength
            dataAckPack = Packet(type=dataAck, seq=rawPack.seq, ack=newAck, window=400)
            clientSocket.sendto(dataAckPack.pack(), clientAddress)
            print(f"--->[{curTime}]响应 ack:{newAck} dataAck报文给{clientAddress}")

        #客户端发送fin请求
        if rawPack.type == fin:
            print(f"[{curTime}] 收到来自{clientAddress}的fin请求")
            finAckPack = Packet(type=finAck, seq=rawPack.seq, ack=rawPack.ack + 1, window=400)
            clientSocket.sendto(finAckPack.pack(), clientAddress)
            print(f"--->[{curTime}]响应finAck报文给{clientAddress}")
            return


class ThreadedUDPServer(socketserver.ThreadingUDPServer):
    #使用socketserver库创建多线程UDP服务器。每当有新的请求，服务器会创建一个新的线程来处理，避免阻塞主线程。
    def __init__(self, server_address, RequestHandlerClass):
        super().__init__(server_address, RequestHandlerClass)
        print(f"UDP 服务器已启动，监听在 {server_address[0]}:{server_address[1]}")


server = ThreadedUDPServer((serverIP, serverPort), clientHandeler)
try:
    server.serve_forever()
except KeyboardInterrupt:
    print("\n服务器正在关闭...")
finally:
    server.shutdown()
    server.server_close()