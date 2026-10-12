from proto.uid_generator_pb2 import uid_generator
from proto.like_pb2 import like
from proto.visit_count_pb2 import Info
from google.protobuf.message import DecodeError


def create_like_protobuf(user_id, region):
    """Build like request protobuf."""
    try:
        message = like()
        message.uid = int(user_id)
        message.region = region
        return message.SerializeToString()
    except Exception:
        return None


def create_uid_protobuf(uid):
    """Build UID request protobuf (GetPlayerPersonalShow)."""
    try:
        msg = uid_generator()
        msg.saturn_ = int(uid)     # field 1
        msg.garena = 1             # field 2  ⚠️ MUST
        return msg.SerializeToString()
    except Exception:
        return None


def decode_protobuf(binary):
    """Parse response — NESTED AccountInfo now."""
    try:
        msg = Info()
        msg.ParseFromString(binary)
        return msg
    except DecodeError as e:
        print(f"[PROTOBUF DECODE ERROR] {e}")
        return None
    except Exception as e:
        print(f"[UNEXPECTED ERROR] {e}")
        return None