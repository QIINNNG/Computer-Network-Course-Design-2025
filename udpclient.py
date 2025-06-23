import random
import socket
import struct
import time
import pandas as pd
from datetime import datetime

serverIP = "127.0.0.1"
serverPort = 8080
headerFormat = "!BIIHH"
headerLength = struct.calcsize(headerFormat)

windowSize = 400
minPacket = 40
maxPacket = 80
defaultRTT = 100
rawDataLength = 3000

syn = 0x00
synAck = 0x01
dataFlow = 0x02
dataAck = 0x03
fin = 0x04
finAck = 0x05

totalRTT = [] #存储每次成功确认的RTT值
packetSend = 0 #记录总共发送的数据包次数（包括重传）
packNum = 0 #记录原始数据被分成的包的数量
packetAcked = 0
packetResend = 0
maxRetry = 5 #每个数据包的最大重试次数


class Packet:
    """
    将 Packet 对象打包成字节串，用于网络传输。
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





class clientHandeler:
    def __init__(self, server_ip, server_port):
        self.serverAddress = (server_ip, server_port)
        self.clientSocket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.clientSocket.settimeout(0.05) #设置超时时间为50ms
        self.rawPacket = Packet()
        self.rawData = b''
        self.sendBase = 0  #发送窗口的起始字节序列号(已确认的最后一个字节的下一个字节)
        self.nextSeq = 0  #下一个要发送的字节流的起始序列号
        # 存储未确认的数据包: {序列号: {'packet':, 'start_byte': , 'end_byte': , 'timeSend': , 'retries': , 'packNum':}}
        self.unackPackets = {}


    def connect(self):
        synPack = Packet(type=syn)
        self.clientSocket.sendto(synPack.pack(), self.serverAddress)
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]发送syn包 (序列号: {0})。")
        recData, _ = self.clientSocket.recvfrom(2048)
        self.rawPacket.unpack(recData)
        if self.rawPacket.type == synAck:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]接收synACK包 (序列号: {self.rawPacket.seq})。")
            self.sendBase = self.rawPacket.ack
            self.nextSeq = self.sendBase
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]错误: 响应包类型错误。")
            return False
        return  True

    def sendDataPack(self, data):
        global packetSend, packNum
        sendST = self.nextSeq
        newData = Packet(type=dataFlow, seq=sendST, ack=self.sendBase, window=400 ,data=data)
        self.clientSocket.sendto(newData.pack(), self.serverAddress)
        packetSend += 1
        #记录未确认的数据包信息
        self.unackPackets[self.nextSeq]={'packet': newData, 'start_byte': self.nextSeq,
                                         'end_byte': self.nextSeq + len(newData.data) - 1,
                                         'timeSend': time.time(), 'retries': 0, 'packNum': packNum}
        curTime = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{curTime}]第{packetSend}个数据包 {sendST}~{sendST + len(data) - 1} 字节已发送。")
        self.nextSeq += len(data)
    def checkResend(self):
        global packetSend, packetResend
        current_time = time.time()
        resend_list = []

        #检查所有未确认的分组是否超时
        for seq in list(self.unackPackets.keys()):
            packet_data = self.unackPackets[seq]
            elapsed_time = (current_time - packet_data['timeSend']) * 1000

            #如果分组超时且未达到最大重试次数
            if elapsed_time > defaultRTT and packet_data['retries'] < maxRetry:
                resend_list.append(seq)
            elif packet_data['retries'] >= maxRetry:
                #达到最大重试次数的分组直接放弃
                print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 分组 {seq} 达到最大重试次数，放弃")
                self.unackPackets.pop(seq, None)

        #重传所有超时的分组
        for seq in sorted(resend_list):
            packet = self.unackPackets[seq]
            self.clientSocket.sendto(packet['packet'].pack(), self.serverAddress)
            packet['timeSend'] = time.time()
            packet['retries'] += 1
            packetResend += 1
            packetSend += 1
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 重传 seq={seq} (尝试次数: {packet['retries']})")

    def recvAck(self):
        try:
            global packetAcked, packetSend
            replyData, _ = self.clientSocket.recvfrom(2048)
            replyPacket = Packet ()
            replyPacket.unpack(replyData)
            if replyPacket.type == dataAck:
                curTime = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                ackedSeq = replyPacket.ack

                #查找所有已确认的数据包并移除
                packetToRemove = []
                for seqNum in sorted(list(self.unackPackets.keys())):
                    if seqNum < ackedSeq:
                        ackedPacket = self.unackPackets[seqNum]
                        #仅计算未重传包的RTT
                        if ackedPacket['retries'] == 0:
                            RTT = (time.time() - ackedPacket['timeSend']) * 1000
                            totalRTT.append(RTT)
                            print(f"[{curTime}]第{packetSend}个，{ackedPacket['start_byte']}~{ackedPacket['end_byte']}字节 server端已收到，RTT是{RTT:.2f} ms。")
                        else :
                            print(f"[{curTime}]第{packetSend}个，{ackedPacket['start_byte']}~{ackedPacket['end_byte']}字节 重传的包 server端已收到。")

                        packetToRemove.append(seqNum)
                        packetAcked += 1
                    else:
                        break

                #移除已确认的数据包
                for key in packetToRemove:
                    self.unackPackets.pop(key)

                self.sendBase = ackedSeq

                curTime = datetime.now().strftime('%H:%M:%S.%f')[:-3]
                print(f"[{curTime}]窗口滑动：send_base更新为{self.sendBase}。")

        except socket.timeout:
            #在超时时间内没有收到 ACK，由checkResend处理重传
            pass

    def transfer (self):
        global packNum
        self.rawData = b"ABC" * (rawDataLength // 3)
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 开始传输数据。")
        #循环发送数据直到所有数据发送并确认
        while self.sendBase < len(self.rawData) or self.unackPackets:
            while (self.nextSeq - self.sendBase < windowSize) and (self.nextSeq < len(self.rawData)):
                packetSize = random.randint(minPacket, maxPacket)
                dataPack = self.rawData[self.nextSeq:self.nextSeq + packetSize]
                if not dataPack:
                    break

                packNum += 1
                self.sendDataPack(dataPack)
            self.checkResend()
            self.recvAck()

            # 如果窗口已满且无未确认分组，等待
            if (self.nextSeq - self.sendBase >= windowSize) and not self.unackPackets:
                time.sleep(0.01)  # 等待 ACK 释放窗口

        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}] 所有 {len(self.rawData)} 字节数据已发送并确认。")

    def closeConnect(self):
        finPack = Packet(type=fin, seq=self.nextSeq, ack=self.sendBase)
        self.clientSocket.sendto(finPack.pack(), self.serverAddress)
        print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]发送fin。")
        replyData, _ = self.clientSocket.recvfrom(2048)
        replyFinPacket = Packet()
        replyFinPacket.unpack(replyData)
        if replyFinPacket.type == finAck:
            print(f"[{datetime.now().strftime('%H:%M:%S.%f')[:-3]}]收到finACK，连接已终止。")

    def printSummary(self):
        global totalRTT
        RTTS = pd.Series(totalRTT)
        print("====汇总====\n")
        print(f"应发送数据包数: {packNum}")
        print(f"实际发送数据包数: {packetSend}")
        print(f"丢包率为:{packetResend/packetSend * 100}%")
        print(f"maxRTT为: {RTTS.max():.2f} ms")
        print(f"minRTT为: {RTTS.min():.2f} ms")
        print(f"平均RTT为: {RTTS.mean():.2f} ms")
        print(f"RTT标准差为: {RTTS.std():.2f} ms")




server_ip = input("请输入服务器IP地址 (默认: 127.0.0.1): ")
server_port = int(input("请输入服务器端口 (默认: 8080): "))

client = clientHandeler(server_ip, server_port)

try:
    if client.connect():
        client.transfer()
    else:
        print("无法与服务器建立连接，客户端退出。")

except Exception as e:
    print("\n客户端已中断。")
finally:
    client.closeConnect()
    client.printSummary()

