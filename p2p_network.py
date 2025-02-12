# p2p_network.py
import ssl
import socket
import stomp
import logging

logger = logging.getLogger(__name__)

class SecureP2PClient:
    def __init__(self, config):
        self.config = config
        self.peers = self.config['network']['bootstrapping_peers']
        self.use_encryption = self.config['network'].get('use_encryption', True)
        self.context = None

        if self.use_encryption:
            self.context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            self.context.load_verify_locations('SSL/cert.pem')  # Or trust store

    def connect_to_peers(self):
        for peer in self.peers:
            # Just an example: open a secure socket to each peer
            try:
                host, _, port = peer.partition(':')
                port = int(port) if port else 8000
                with socket.create_connection((host, port)) as sock:
                    if self.use_encryption and self.context:
                        with self.context.wrap_socket(sock, server_hostname=host) as ssock:
                            logger.info(f"Connected securely to peer {peer}")
                    else:
                        logger.info(f"Connected (unencrypted) to peer {peer}")
            except Exception as e:
                logger.error(f"Error connecting to peer {peer}: {e}")

class StompServerClient:
    """
    Simple demonstration of STOMP usage.
    Typically, you'd run a STOMP server (like ActiveMQ or RabbitMQ with STOMP plugin).
    """
    def __init__(self, host, port):
        self.host = host
        self.port = port
        self.conn = stomp.Connection([(self.host, self.port)])
        self.conn.set_listener('', PrintingListener())

    def start(self):
        try:
            self.conn.connect(wait=True)
            logger.info("STOMP client connected.")
        except Exception as e:
            logger.error(f"STOMP connection error: {e}")

    def send_message(self, destination, message):
        self.conn.send(destination=destination, body=message)

    def subscribe(self, destination):
        self.conn.subscribe(destination=destination, id=1, ack='auto')

    def disconnect(self):
        self.conn.disconnect()

class PrintingListener(stomp.ConnectionListener):
    def on_error(self, frame):
        print('received an error "%s"' % frame.body)

    def on_message(self, frame):
        print('received a message "%s"' % frame.body)
