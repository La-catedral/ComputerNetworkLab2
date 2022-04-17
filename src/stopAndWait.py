from socket import *
import pkt_format
import time
import threading
import select
import random

"""
停等，双向数据传输，C/S架构文件传输
"""


TIME_OUT = 3   # 超时时间
SEND_WIN_SIZE = 1  # 滑动窗口大小
max_seq_num = 16  # 最大序列号的数目
CLIENT_IP = "127.0.0.1"
SERVER_IP = '127.0.0.1'
CLIENT_PORT_REC = 10240
SERVER_PORT_SEN = 10241
CLIENT_PORT_SEN = 10242
SERVER_PORT_REC = 10243

class GBNClient:
    def __init__(self):
        self.timer = 0  # 计时器，开始计时后超过TIME_OUT则重传
        self.base = 0  #
        self.next_seq = 0
        self.expec_seq = 0
        self.send_win = SEND_WIN_SIZE
        self.send_soc = socket(AF_INET, SOCK_DGRAM)
        self.send_soc.bind((CLIENT_IP, CLIENT_PORT_SEN))
        self.recv_soc = socket(AF_INET,SOCK_DGRAM)
        self.recv_soc.bind((CLIENT_IP,CLIENT_PORT_REC))
        self.lock = threading.Lock()
        self.data_cache_sent = []  # 缓存发送窗口中未被确认的分组
        self.ack_loss_rate = 0.1  # ack发送丢包率
        self.send_loss_rate = 0.1  # 客户端向服务器端发送数据分组时的丢包概率

    def client_send(self,remote_ip = SERVER_IP,remote_port=SERVER_PORT_REC):
        """
        发送报文给服务器
        :return:
        """
        remote_addr = (remote_ip, remote_port)  # 数据将要发送的目标主机，即服务器
        while True:
            time.sleep(random.random()*0.5)
            self.lock.acquire()
            if self.base + self.send_win < max_seq_num:
                if self.next_seq < self.base + self.send_win:
                    data = "the seq of this mes is :" + str(self.next_seq)
                    new_pkt = pkt_format.data_pkt(self.next_seq, data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    print("客户端已发送数据：" + data)
                    if self.next_seq == self.base:
                        self.timer = 0  # 如果窗口为空 开始计时
                    self.next_seq += 1
                    self.data_cache_sent.append(new_pkt)
                # else:
                    # print("客户端滑动窗口已满，暂时无法发送数据")
            else:  # 如果base+滑动窗口大小已经超过最大序号，则需要根据next_seq判断是否发报文
                if self.base <= self.next_seq < max_seq_num:  # 可发送
                    data = "the seq of this mes is :" + str(self.next_seq)
                    new_pkt = pkt_format.data_pkt(self.next_seq, data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    print("客户端已发送数据：" + data)
                    self.data_cache_sent.append(new_pkt)
                    if self.next_seq == self.base:
                        self.timer = 0
                    self.next_seq = (self.next_seq + 1) % max_seq_num
                else:  # next_seq 进行过模运算，按如下模式进行窗口是否已满的判断
                    if self.next_seq < (self.base + self.send_win) % max_seq_num:
                        data = "the seq of this mes is :" + str(self.next_seq)
                        new_pkt = pkt_format.data_pkt(self.next_seq, data)
                        if random.random() > self.send_loss_rate:  # 随机发送丢包
                            self.send_soc.sendto(new_pkt, remote_addr)
                        print("客户端已发送数据：" + data)
                        self.data_cache_sent.append(new_pkt)
                        self.next_seq += 1
                    # else:
                    #     print("客户端滑动窗口已满，暂时无法发送数据")
            self.lock.release()
        return

    def client_recvACK(self):
        """
        另一个线程
        :return:
        """
        while True:
            readable = select.select([self.send_soc], [], [], 1)[0]
            if len(readable) > 0:  # 接收ACK数据
                ack_byte, remote_addr = self.send_soc.recvfrom(2048)
                ack_seq = int(ack_byte.decode().split()[1])
                self.lock.acquire()
                if (self.next_seq < self.base and (ack_seq >= self.base or ack_seq < self.next_seq)) \
                        or (self.next_seq > ack_seq >= self.base):  # 确保ack在等待相应序列号范围内
                    if ack_seq >= self.base:
                        self.data_cache_sent = self.data_cache_sent[ack_seq + 1 - self.base:]
                    else:
                        self.data_cache_sent = self.data_cache_sent[ack_seq + 1 + max_seq_num - self.base:]
                    self.timer = 0  # 每收到一个ack，重启定时器
                    self.base = (ack_seq + 1) % max_seq_num
                self.lock.release()
            else:
                self.timer += 1
                if self.timer > TIME_OUT:
                    self.timeout_resend(SERVER_IP,SERVER_PORT_REC)
        return

    def receive_from_server(self):
        while True:
            readable = select.select([self.recv_soc,],[],[],1)[0]
            if len(readable)> 0:
                rec_pkt,addr = self.recv_soc.recvfrom(1024)
                seq = int(rec_pkt.decode().split()[0])
                data = rec_pkt.decode().replace(str(seq)+' ','')
                if seq == self.expec_seq:  # 按序收到了报文段
                    if random.random() > self.ack_loss_rate:
                        self.recv_soc.sendto(pkt_format.ack_pkt(self.expec_seq),(SERVER_IP,SERVER_PORT_SEN))
                    print("客户端确认收到数据：" + data)
                    file = open('client_file.txt', 'a')
                    file.write(data)
                    file.close()
                    self.expec_seq = (self.expec_seq + 1) % max_seq_num
                else:  # 发送期待收到的报文序列号
                    if random.random() > self.ack_loss_rate:
                        self.recv_soc.sendto(pkt_format.ack_pkt(self.expec_seq - 1), (SERVER_IP, SERVER_PORT_SEN))
                    print("客户端重新确认序列号" + str(self.expec_seq - 1))

    def timeout_resend(self,remote_ip,remote_port):
        print("客户端响应超时，重新发送：")
        self.timer = 0
        for pkt in self.data_cache_sent:
            self.send_soc.sendto(pkt, (remote_ip, remote_port))
            print("客户端已重新发送："+pkt.decode())





class GBNServer:
    """
    实现了超时重传 随机丢包 ack确认等机制
    """

    def __init__(self):
        self.timer = 0  # 计时器，开始计时后超过TIME_OUT则重传
        self.base = 0  #
        self.next_seq = 0
        self.expec_seq = 0
        self.send_win = SEND_WIN_SIZE
        self.send_soc = socket(AF_INET, SOCK_DGRAM)
        self.send_soc.bind((SERVER_IP, SERVER_PORT_SEN))
        self.recv_soc = socket(AF_INET, SOCK_DGRAM)
        self.recv_soc.bind((SERVER_IP, SERVER_PORT_REC))
        self.lock = threading.Lock()
        self.data_cache_sent = []
        self.send_loss_rate = 0.1  # 发送数据包时的丢包概率
        self.ack_loss_rate = 0.1  # 发给客户端的ack的丢包率

    def server_send(self, remote_ip = CLIENT_IP, remote_port=CLIENT_PORT_REC):
        """
        发送报文给有需求的客户端
        :remote_ip:客户端的ip
        :remote_port:客户端的端口号
        :return: none
        """
        remote_addr = (remote_ip, remote_port)  # 数据将要发送的目标主机，即客户端
        file = open("server_file.txt")
        i = 0
        #每发送一个数据段
        while True:
            time.sleep(random.random()*0.5)

            self.lock.acquire()
            if self.base + self.send_win < max_seq_num:
                if self.next_seq < self.base+self.send_win :
                    data = file.readline()
                    if data == '':
                        break
                    new_pkt = pkt_format.data_pkt(self.next_seq,data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    print("服务器已发送："+ data)
                    if self.next_seq == self.base:
                        self.timer = 0  # 如果窗口为空 开始计时
                    self.next_seq += 1
                    self.data_cache_sent.append(new_pkt)
            else:  # 如果base+滑动窗口大小已经超过最大序号，则需要根据next_seq判断是否发报文
                if self.base <= self.next_seq < max_seq_num:  # 可发送
                    data = file.readline()
                    if data == '':
                        break
                    new_pkt = pkt_format.data_pkt(self.next_seq,data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    print("服务器已发送：" + data)
                    self.data_cache_sent.append(new_pkt)
                    if self.next_seq == self.base:
                        self.timer = 0
                    self.next_seq = (self.next_seq + 1) % max_seq_num
                else:  # next_seq 进行过模运算，按如下模式进行窗口是否已满的判断
                    if self.next_seq < (self.base + self. send_win) % max_seq_num:
                        data = file.readline()
                        if data == '':
                            break
                        new_pkt = pkt_format.data_pkt(self.next_seq,data)
                        if random.random() > self.send_loss_rate:  # 随机发送丢包
                            self.send_soc.sendto(new_pkt, remote_addr)
                        print("服务器已发送：" + data)
                        self.data_cache_sent.append(new_pkt)
                        self.next_seq += 1
            self.lock.release()
        return

    def server_recvACK(self):
        """
        另一个线程
        :return:
        """
        while True:
            readable = select.select([self.send_soc], [], [], 1)[0]
            if len(readable) > 0:  # 接收ACK数据
                ack_byte,remote_addr = self.send_soc.recvfrom(2048)
                ack_seq = int (ack_byte.decode().split()[1])
                self.lock.acquire()
                if (self.next_seq < self.base and (ack_seq > self.base or ack_seq < self.next_seq)) \
                    or (self.next_seq > ack_seq >= self.base):  # 确保ack在等待相应序列号范围内
                    if ack_seq >= self.base:
                        self.data_cache_sent = self.data_cache_sent[ack_seq + 1 - self.base:]
                    else:
                        self.data_cache_sent = self.data_cache_sent[ack_seq + 1 + max_seq_num - self.base:]
                    self.base = (ack_seq + 1) % max_seq_num
                self.lock.release()
            else:
                self.timer += 1
                if self.timer > TIME_OUT:
                    self.timeout_resend(CLIENT_IP,CLIENT_PORT_REC)

        return

    def timeout_resend(self,remote_ip,remote_port):
        print("客户端响应超时，重新发送：")
        self.timer = 0
        for pkt in self.data_cache_sent:
            self.send_soc.sendto(pkt, (remote_ip, remote_port))
            print("服务器已重新发送："+pkt.decode())

    def receive_from_client(self):
        while True:
            readable = select.select([self.recv_soc, ], [], [], 1)[0]
            if len(readable) > 0:
                rec_pkt,addr = self.recv_soc.recvfrom(1024)
                data = rec_pkt.decode()
                seq = int(data.split()[0])
                if seq == self.expec_seq:  # 按序收到了报文段
                    if random.random() > self.ack_loss_rate:
                        self.recv_soc.sendto(pkt_format.ack_pkt(self.expec_seq), (CLIENT_IP, CLIENT_PORT_SEN))
                    print("服务器确认收到数据：" + data)
                    self.expec_seq = (self.expec_seq + 1) % max_seq_num
                else:  # 发送期待收到的报文序列号
                    if random.random() > self.ack_loss_rate:
                        self.recv_soc.sendto(pkt_format.ack_pkt(self.expec_seq-1), (CLIENT_IP, CLIENT_PORT_SEN))
                    print("服务器重新确认序列号" + str(self.expec_seq-1))

#
client = GBNClient()
server = GBNServer()

print("服务器开始向客户端发送数据：")
server_sendat_thread = threading.Thread(target=server.server_send)
server_recvack_thread = threading.Thread(target=server.server_recvACK)  # server发送数据与接收ack同时进行
client_recvdat_thread = threading.Thread(target=client.receive_from_server)
client_recvdat_thread.start()
server_recvack_thread.start()
server_sendat_thread.start()
#
# print("客户端开始向服务器发送数据：")
# client_sendat_thread = threading.Thread(target=client.client_send)
# client_recvack_thread = threading.Thread(target=client.client_recvACK)  # server发送数据与接收ack同时进行
# server_recvdat_thread = threading.Thread(target=server.receive_from_client)
# server_recvdat_thread.start()
# client_recvack_thread.start()
# client_sendat_thread.start()
#