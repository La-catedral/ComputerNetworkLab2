from socket import *
import time
import threading
import pkt_format
import random
import select


WIN_SIZE = 4
max_seq_num = 16
TIME_OUT = 3   # 超时时间
CLIENT_IP = "127.0.0.1"
SERVER_IP = '127.0.0.1'
CLIENT_PORT = 10247
SERVER_PORT = 10248


class SRServer:
    def __init__(self):
        self.base = 0
        self.send_win = WIN_SIZE  # 滑动窗口大小
        self.next_seq = 0
        self.send_soc = socket(AF_INET, SOCK_DGRAM)
        self.send_soc.bind((SERVER_IP, SERVER_PORT))
        self.lock = threading.Lock()
        self.data_cache_sent = {}  # 缓存发送窗口中未被确认的分组 由序号作为键值索引
        self.send_loss_rate = 0.1  # 客户端向服务器端发送数据分组时的丢包概率
        self.timer = {}  # 所有时钟

    def server_send(self):
        """
        向客户端发送数据
        :return: none
        """
        remote_addr = (CLIENT_IP, CLIENT_PORT)
        while True:
            time.sleep(random.random() * 0.5)
            self.lock.acquire()
            if self.base + self.send_win < max_seq_num:
                if self.next_seq < self.base + self.send_win:
                    data = "the seq of this mes is :" + str(self.next_seq)
                    new_pkt = pkt_format.data_pkt(self.next_seq, data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    self.timer[self.next_seq] = 0  # 为该序号对应的分组启动定时器
                    print("服务器端已发送数据：" + data)
                    self.data_cache_sent[self.next_seq] = new_pkt
                    self.next_seq += 1
                else:
                    print("服务器端滑动窗口已满，暂时无法发送数据")
            else:  # 如果base+滑动窗口大小已经超过最大序号，则需要根据next_seq判断是否发报文
                if self.base <= self.next_seq < max_seq_num:  # 可发送
                    data = "the seq of this mes is :" + str(self.next_seq)
                    new_pkt = pkt_format.data_pkt(self.next_seq, data)
                    if random.random() > self.send_loss_rate:  # 随机发送丢包
                        self.send_soc.sendto(new_pkt, remote_addr)
                    print("服务器端已发送数据：" + data)
                    self.data_cache_sent[self.next_seq] = new_pkt
                    self.timer[self.next_seq] = 0  # 为该序号对应的分组启动定时器
                    self.next_seq = (self.next_seq + 1) % max_seq_num
                else:  # next_seq 进行过模运算，按如下模式进行窗口是否已满的判断
                    if self.next_seq < (self.base + self.send_win) % max_seq_num:
                        data = "the seq of this mes is :" + str(self.next_seq)
                        new_pkt = pkt_format.data_pkt(self.next_seq, data)
                        if random.random() > self.send_loss_rate:  # 随机发送丢包
                            self.send_soc.sendto(new_pkt, remote_addr)
                        print("服务器端已发送数据：" + data)
                        self.timer[self.next_seq] = 0  # 为该序号对应的分组启动定时器
                        self.data_cache_sent[self.next_seq] = new_pkt
                        self.next_seq += 1
                    else:
                        print("服务器端滑动窗口已满，暂时无法发送数据")
            self.lock.release()
        return
    def server_recvAck(self):
        """
        从客户端接收ACK
        :return: none
        """
        while True:
            readable = select.select([self.send_soc], [], [], 1)[0]
            if len(readable) > 0:  # 接收ACK数据
                ack_byte, remote_addr = self.send_soc.recvfrom(2048)
                ack_seq = int(ack_byte.decode().split()[1])
                print(ack_byte.decode())
                self.lock.acquire()
                if (self.next_seq < self.base and (ack_seq > self.base or ack_seq < self.next_seq)) \
                    or (self.next_seq > ack_seq >= self.base):  # 确保ack在等待相应序列号范围内
                    self.data_cache_sent.pop(ack_seq)  # 删除发送缓存中该序号对应的分组
                    self.timer.pop(ack_seq)  # 停止相应时钟
                    if bool(self.data_cache_sent):  # 如果还有已发送未确认的分组
                        self.base = list(self.data_cache_sent.keys())[0]  # 最先加入的还没有被ack的序号
                    else:
                        self.base = (self.base + 1) % max_seq_num
                self.lock.release()
            else:
                for data in self.timer.keys():
                    self.timer[data] += 1
                    if self.timer[data] > TIME_OUT:
                        print("客户端响应超时，重新发送")
                        self.timer[data] = 0
                        self.send_soc.sendto(self.data_cache_sent[data], (CLIENT_IP,CLIENT_PORT))
                        print("服务器已重新发送：" + self.data_cache_sent[data].decode())

        return


class SRClient:
    def __init__(self):
        self.recv_base = 0
        self.recv_win = WIN_SIZE  # 滑动窗口大小
        self.recv_soc = socket(AF_INET, SOCK_DGRAM)
        self.recv_soc.bind((CLIENT_IP, CLIENT_PORT))
        self.recv_cache = {}  # 缓存接收的分组
        self.ack_loss_rate = 0.1  # 客户端向服务器端发送ack时的丢包概率

    def client_recv(self):
        remote_addr = (SERVER_IP,SERVER_PORT)
        while True:
            readable = select.select([self.recv_soc], [], [], 1)[0]
            if len(readable) > 0:
                rec_pkt, addr = self.recv_soc.recvfrom(1024)
                data = rec_pkt.decode()
                seq = int(data.split()[0])
                self.recv_cache[seq] = rec_pkt
                if seq == self.recv_base:
                    if random.random() > self.ack_loss_rate:  # 发送ack进行确认
                        self.recv_soc.sendto(pkt_format.ack_pkt(seq), remote_addr)
                    seq_num = seq  # 循环向应用层传输按序的数据分组
                    while seq_num in self.recv_cache.keys():
                        print("客户端确认收到数据：" + self.recv_cache[seq_num].decode())
                        self.recv_cache.pop(seq_num)
                        seq_num = (seq_num + 1) % max_seq_num
                    self.recv_base = (seq_num + 1) % max_seq_num
                elif (seq >= self.recv_base and self.recv_base + self.recv_win <= max_seq_num) \
                        or (self.recv_base + self.recv_win > max_seq_num and (seq >= self.recv_base or seq < (self.recv_base + self.recv_win) % max_seq_num)):
                    self.recv_cache[seq] = rec_pkt  # 缓存乱序到达的分组
                    if random.random() > self.ack_loss_rate:  # 发送ack进行确认
                        self.recv_soc.sendto(pkt_format.ack_pkt(seq), remote_addr)
                else:  # 重新接收到已经接受过的分组 直接发送ack
                    if random.random() > self.ack_loss_rate:  # 发送ack进行确认
                        self.recv_soc.sendto(pkt_format.ack_pkt(seq), remote_addr)
        return


client = SRClient()
server = SRServer()

print("服务器开始向客户端发送数据：")
server_sendata_thread = threading.Thread(target=server.server_send)
server_recvack_thread = threading.Thread(target=server.server_recvAck)  # server发送数据与接收ack同时进行
client_recvdat_thread = threading.Thread(target=client.client_recv)
client_recvdat_thread.start()
server_recvack_thread.start()
server_sendata_thread.start()

time.sleep(60)
client.recv_soc.close()
server.send_soc.close()
exit(0)