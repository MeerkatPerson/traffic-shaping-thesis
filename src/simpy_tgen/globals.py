TGEN_MMODEL_DELAY_CEILING = (1000*1000*60*10)

# /proc/sys/net/ipv4/tcp_wmem on debian 11
TCP_WMEM_DEFAULT_SIZE = 16384

DEFAULT_STREAM_READ_BUFLEN = 65536
DEFAULT_STREAM_WRITE_BUFLEN = 32768

# this is how many bytes we send for each packet type observation
TGEN_MMODEL_PACKET_DATA_SIZE = 1434

# our header for data-cells currently looks like this: "DATA|parent_flow_id|stream_id|cell_num", e.g. "DATA|9999|9999|999999". This example is 19 bytes long, so 19 bytes should be sufficient since our ids aren't expected to have more than 4 digits and we probably also won't send more than 999999 cells on a stream
HEADER_LEN = 22
PAYLOAD_LEN = 492
CELL_SIZE = 514

# packets sent within this many microseconds will be sent at the same time for efficiency reasons (in tgen)
TGEN_MMODEL_MICROS_AT_ONCE = 10000

MICROSECONDS_PER_SECOND = 1000000
