

def data_pkt(seq,data):
    """
    结构为："seq+' '+data" 的形式，比如"2 hello"
    :param seq: 序列号
    :param data: 数据段
    :return:编码后的具有固定格式的报文
    """
    data_pk = (str(seq) + ' ' + data).encode()
    return data_pk

def ack_pkt(ACK_seq):
    """
    结构为"ACK+' '+ACK_seq"的形式，比如"ACK 2"
    :param ACK_seq: 最后一个确认的序列号
    :return: 编码后的具有固定格式的ack报文
    """
    ack_pk = ("ACK" + ' ' + str(ACK_seq)).encode()
    return ack_pk


