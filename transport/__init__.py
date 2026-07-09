"""Vehicle transport backends behind a single interface.

    from transport import Transport, EcuResponse, FakeTransport
    from transport.socketcan import SocketCanTransport   # Linux + can-isotp
    from transport.elm327 import Elm327Transport         # (secondary backend, TBD)
"""
from .base import EcuResponse, Transport, TransportError
from .fake import FakeTransport

__all__ = ["Transport", "EcuResponse", "TransportError", "FakeTransport"]
